"""Local diagnostic harness wrapping src/agents/ call logs into strands-evals
Session traces, per docs/ImplementationPlan.md Sprint 4.

The spec named a flat `Session` / `detect_failures` / `analyze_root_cause` API.
The actual installed package (`strands-agents-evals` 1.3.0, imported as
`strands_evals`) has real, close-but-not-identical primitives, confirmed by
direct introspection in this environment:

    strands_evals.types.trace.Session(traces=[...], session_id=...)
    strands_evals.types.trace.Trace(spans=[...], trace_id=..., session_id=...)
    strands_evals.types.trace.AgentInvocationSpan(span_info=..., user_prompt=...,
        agent_response=..., available_tools=[...], system_prompt=...)
    strands_evals.types.trace.SpanInfo(session_id=..., start_time=..., end_time=...)
    strands_evals.detectors.detect_failures(session, ...) -> FailureOutput
    strands_evals.detectors.analyze_root_cause(session, failures=None, ...) -> RCAOutput

This module builds real Session/Trace/AgentInvocationSpan objects when the
package is available, and falls back to minimal local equivalents (same shape,
no LLM-judge diagnosis) when it isn't -- per CLAUDE.md's "Unverified External
Packages" policy. `detect_fn`/`analyze_fn` are always injectable so tests never
require a live model call.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

try:
    from strands_evals.detectors import analyze_root_cause as _real_analyze_root_cause
    from strands_evals.detectors import detect_failures as _real_detect_failures
    from strands_evals.types.trace import AgentInvocationSpan, SpanInfo, Trace
    from strands_evals.types.trace import Session as _StrandsSession

    STRANDS_EVALS_AVAILABLE = True
except ImportError:
    STRANDS_EVALS_AVAILABLE = False


@dataclass
class AgentCallRecord:
    """One agent invocation, as logged by the orchestrator/agent layer, ready
    to be wrapped into a strands-evals Session for offline diagnosis."""

    agent_name: str
    system_prompt: str
    user_prompt: str
    response: str
    start_time: datetime
    end_time: datetime


@dataclass
class DiagnosisResult:
    """Local, stable result shape returned by `diagnose()` regardless of
    whether the real strands-evals package or the local fallback ran --
    callers never need to know which path executed."""

    failures: list[str] = field(default_factory=list)
    root_causes: list[str] = field(default_factory=list)


# --- Fallback session shape (used only if strands_evals isn't importable) --


@dataclass
class _FallbackSpan:
    agent_name: str
    user_prompt: str
    agent_response: str
    start_time: datetime
    end_time: datetime


@dataclass
class _FallbackTrace:
    spans: list[_FallbackSpan]
    trace_id: str
    session_id: str


@dataclass
class _FallbackSession:
    session_id: str
    traces: list[_FallbackTrace]


def build_session(session_id: str, records: list[AgentCallRecord]):
    """Wrap `records` (one per agent call in a single orchestrator run) into a
    single-trace Session. Returns a real strands_evals Session when the
    package is available, otherwise the shape-compatible local fallback.
    """
    if STRANDS_EVALS_AVAILABLE:
        spans = []
        for record in records:
            span_info = SpanInfo(
                session_id=session_id,
                trace_id=session_id,
                span_id=str(uuid.uuid4()),
                start_time=record.start_time,
                end_time=record.end_time,
            )
            spans.append(
                AgentInvocationSpan(
                    span_info=span_info,
                    system_prompt=record.system_prompt,
                    user_prompt=record.user_prompt,
                    agent_response=record.response,
                    available_tools=[],
                    metadata={"agent_name": record.agent_name},
                )
            )
        trace = Trace(spans=spans, trace_id=session_id, session_id=session_id)
        return _StrandsSession(traces=[trace], session_id=session_id)

    spans = [
        _FallbackSpan(
            agent_name=r.agent_name,
            user_prompt=r.user_prompt,
            agent_response=r.response,
            start_time=r.start_time,
            end_time=r.end_time,
        )
        for r in records
    ]
    trace = _FallbackTrace(spans=spans, trace_id=session_id, session_id=session_id)
    return _FallbackSession(session_id=session_id, traces=[trace])


def _fallback_detect_failures(session) -> list[str]:
    """Heuristic failure detector used only when strands-evals is unavailable:
    flags any span whose response doesn't look like a JSON object, mirroring
    the same MalformedAgentOutput condition src/core/ollama_client.py checks."""
    failures = []
    for trace in session.traces:
        for span in trace.spans:
            response = getattr(span, "agent_response", "")
            stripped = response.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                agent_name = getattr(span, "agent_name", None) or (getattr(span, "metadata", {}) or {}).get(
                    "agent_name", "unknown"
                )
                failures.append(f"{agent_name}: response does not look like a JSON object")
    return failures


def diagnose(
    session,
    detect_fn: Callable | None = None,
    analyze_fn: Callable | None = None,
    model: str | None = None,
) -> DiagnosisResult:
    """Run failure detection, and root-cause analysis only if failures were
    found (an empty-failures session has nothing to root-cause). `detect_fn`/
    `analyze_fn` default to the real strands-evals detectors when available,
    or the local heuristic fallback otherwise.
    """
    if detect_fn is None:
        if STRANDS_EVALS_AVAILABLE:
            detect_fn = lambda s, **kw: _real_detect_failures(s, model=model, **kw)  # noqa: E731
        else:
            detect_fn = lambda s, **kw: _FallbackDetectResult(_fallback_detect_failures(s))  # noqa: E731

    failure_output = detect_fn(session)
    failures = list(getattr(failure_output, "failures", failure_output) or [])

    if not failures:
        return DiagnosisResult(failures=[], root_causes=[])

    if analyze_fn is None:
        if STRANDS_EVALS_AVAILABLE:
            analyze_fn = lambda s, failures=None, **kw: _real_analyze_root_cause(  # noqa: E731
                s, failures=failures, model=model, **kw
            )
        else:
            analyze_fn = lambda s, failures=None, **kw: _FallbackRcaResult(  # noqa: E731
                [f"(local heuristic, no LLM judge) unresolved: {f}" for f in (failures or [])]
            )

    rca_output = analyze_fn(session, failures=failures)
    root_causes = list(getattr(rca_output, "root_causes", rca_output) or [])

    return DiagnosisResult(failures=failures, root_causes=root_causes)


@dataclass
class _FallbackDetectResult:
    failures: list[str]


@dataclass
class _FallbackRcaResult:
    root_causes: list[str]
