"""CLI entry point: NL idea -> Orchestrator -> review-gated dispatch -> a
formatted 5-part report. Wires together every prior sprint's pieces:
schemas (Sprint 1), scrapers (Sprint 2, optional), the orchestrator/agents
(Sprint 3), the review gate + repair loop (Sprint 4), and context compaction +
event-driven reminders (Sprint 5).

Zero cloud calls: every default chat_fn talks to the local Ollama endpoint
(src/core/config.py); nothing here requires a paid API key.
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from src.agents import orchestrator
from src.core.context_manager import ContextManager
from src.core.ollama_client import ChatFn, ModelUnavailableError
from src.core.schemas import ProductConstraints, ReviewReport
from src.evals.strands_harness import AgentCallRecord
from src.review import repair_loop

AGENT_DISPLAY_NAMES: dict[str, str] = {
    "cofounder": "Co-Founder (Shark Tank Verdict)",
    "product_manager": "Product Manager (PRD)",
    "engineer": "Engineering Lead (Tech Stack)",
    "gtm_ops": "GTM & Research (Market Sentiment)",
    "legal_finance": "Legal/Finance (Compliance Flags)",
}

RunEventFn = Callable[[str, dict], None]
"""(event_type, data) -> None, called synchronously at each pipeline
milestone. Never allowed to break the pipeline -- see `_emit`."""


@dataclass
class PipelineResult:
    constraints: ProductConstraints
    outputs: dict[str, object] = field(default_factory=dict)
    reports: dict[str, ReviewReport] = field(default_factory=dict)
    iterations: dict[str, int] = field(default_factory=dict)
    formatted_output: str = ""
    call_records: list[AgentCallRecord] = field(default_factory=list)
    """Every real chat_fn call made during this run (worker generations and
    rubric judgments alike), in call order. Feeds src/evals/strands_harness.py
    for post-run diagnosis -- see /api/diagnose in src/server.py."""


def _emit(on_event: RunEventFn | None, event_type: str, **data: object) -> None:
    if on_event is None:
        return
    try:
        on_event(event_type, data)
    except Exception:
        # A broken event consumer (e.g. a dropped SSE connection) must never
        # take down the pipeline run itself.
        pass


def _instrument_chat_fn(
    chat_fn: ChatFn,
    agent_name: str,
    role: str,
    on_event: RunEventFn | None,
    records: list[AgentCallRecord],
) -> ChatFn:
    """Wrap `chat_fn` to record every call as an AgentCallRecord (used to
    build the Strands Evals Session after the run) and emit a "chat_call"
    event as it happens (used for the live diagnostics drawer). Wraps ANY
    chat_fn uniformly -- the real Ollama-backed one or a test double -- so
    instrumentation never depends on which is in use.
    """

    def _wrapped(system_prompt: str, user_prompt: str) -> str:
        start = datetime.now(timezone.utc)
        _emit(on_event, "chat_call_start", agent=agent_name, role=role)
        response = chat_fn(system_prompt, user_prompt)
        end = datetime.now(timezone.utc)
        records.append(
            AgentCallRecord(
                agent_name=f"{agent_name}:{role}",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=response,
                start_time=start,
                end_time=end,
            )
        )
        _emit(
            on_event,
            "chat_call_end",
            agent=agent_name,
            role=role,
            duration_ms=round((end - start).total_seconds() * 1000, 1),
        )
        return response

    return _wrapped


def run_pipeline(
    raw_prompt: str,
    parse_chat_fn: ChatFn | None = None,
    chat_fns: dict[str, ChatFn] | None = None,
    review_chat_fn: ChatFn | None = None,
    scraped_context: str | None = None,
    checkpoint_fn: Callable[[ProductConstraints, object], bool] | None = None,
    context_manager: ContextManager | None = None,
    max_repair_iterations: int = 3,
    on_event: RunEventFn | None = None,
) -> PipelineResult:
    """Run the full local pipeline for one natural-language idea prompt.

    Every worker's output is review-gated (Sprint 4's 2-layer gate + bounded
    repair loop) before being included in the result -- a malformed or
    ungrounded output never reaches `formatted_output` silently; it either
    gets repaired within `max_repair_iterations` or `RepairLoopExhausted`
    propagates to the caller.

    `on_event`, if given, is called synchronously at each milestone
    (run_start, parse_start/done, agent_start/chat_call_start/
    chat_call_end/repair_review/agent_done, checkpoint_*, run_done/run_error)
    -- see src/server.py's SSE endpoint for how this drives a live log.
    """
    chat_fns = chat_fns or {}
    context_manager = context_manager or ContextManager()
    call_records: list[AgentCallRecord] = []

    _emit(on_event, "run_start", prompt=raw_prompt)

    context_manager.add_entry("user_prompt", raw_prompt)
    _emit(on_event, "parse_start")
    instrumented_parse_fn = _instrument_chat_fn(
        parse_chat_fn or orchestrator.default_chat_fn(orchestrator.model_for("orchestrator_parse")),
        "orchestrator",
        "parse",
        on_event,
        call_records,
    )
    constraints = orchestrator.parse_constraints(raw_prompt, chat_fn=instrumented_parse_fn)
    context_manager.add_entry("constraints", constraints.model_dump_json())
    _emit(on_event, "parse_done", constraints=constraints.model_dump(mode="json"))

    def _run_fn_for(name: str):
        # repair_loop.repair_until_passing calls run_fn(constraints, chat_fn=..., feedback=...)
        # using the SAME chat_fn it passes to evaluator.evaluate() for the rubric judge.
        # Workers and the rubric judge need different chat_fns (a worker's raw JSON output
        # is not a valid RubricScore), so this wrapper ignores the incoming chat_fn and
        # always uses this agent's own worker_chat_fn -- the rubric's chat_fn is supplied
        # separately as `review_chat_fn` below.
        base_run_fn = orchestrator._WORKER_RUN_FNS[name]
        worker_chat_fn = _instrument_chat_fn(
            chat_fns.get(name) or orchestrator.default_chat_fn(orchestrator.model_for(name)),
            name,
            "generate",
            on_event,
            call_records,
        )

        def _wrapped(constraints: ProductConstraints, chat_fn: ChatFn | None = None, feedback: str | None = None):
            if name == "gtm_ops":
                return base_run_fn(
                    constraints, chat_fn=worker_chat_fn, scraped_context=scraped_context, feedback=feedback
                )
            return base_run_fn(constraints, chat_fn=worker_chat_fn, feedback=feedback)

        return _wrapped

    instrumented_review_fns: dict[str, ChatFn] = {
        name: _instrument_chat_fn(
            review_chat_fn or orchestrator.default_chat_fn(orchestrator.model_for("review_rubric")),
            name,
            "review",
            on_event,
            call_records,
        )
        for name in orchestrator.WORKER_AGENT_NAMES
    }

    def _repair_one(name: str):
        _emit(on_event, "agent_start", agent=name)
        context_manager.build_dispatch_reminder(name)
        try:
            output, report, iterations = repair_loop.repair_until_passing(
                name,
                _run_fn_for(name),
                constraints,
                chat_fn=instrumented_review_fns[name],
                max_iterations=max_repair_iterations,
            )
        except repair_loop.RepairLoopExhausted:
            _emit(on_event, "agent_failed", agent=name)
            raise
        context_manager.add_entry(name, output.model_dump_json())
        _emit(
            on_event,
            "agent_done",
            agent=name,
            iterations=iterations,
            passed=report.passed,
            rubric_score=report.llm_rubric_score,
        )
        return name, output, report, iterations

    outputs: dict[str, object] = {}
    reports: dict[str, ReviewReport] = {}
    iterations: dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=len(orchestrator.WORKER_AGENT_NAMES)) as executor:
        futures = [executor.submit(_repair_one, name) for name in orchestrator.WORKER_AGENT_NAMES]
        for future in futures:
            name, output, report, iters = future.result()
            outputs[name] = output
            reports[name] = report
            iterations[name] = iters

    if checkpoint_fn is not None:
        _emit(on_event, "checkpoint_pending", agent="legal_finance")
        approved = checkpoint_fn(constraints, outputs["legal_finance"])
        _emit(on_event, "checkpoint_result", agent="legal_finance", approved=approved)
        if not approved:
            _emit(on_event, "run_error", reason="legal_finance_checkpoint_blocked")
            raise orchestrator.LegalFinanceCheckpointBlocked(
                "Human-in-the-loop checkpoint declined to release the Legal/Finance agent's output."
            )

    formatted_output = format_output(constraints, outputs)
    _emit(on_event, "run_done", iterations=iterations)
    return PipelineResult(
        constraints=constraints,
        outputs=outputs,
        reports=reports,
        iterations=iterations,
        formatted_output=formatted_output,
        call_records=call_records,
    )


def format_output(constraints: ProductConstraints, outputs: dict[str, object]) -> str:
    """Render the pipeline's constraints + up to 5 worker outputs as a plain
    text report -- not a raw JSON dump, so it reads like a startup team's
    deliverable rather than a debug trace."""
    lines = [
        "# Co-Worker OS — Deliverable Report",
        "",
        f"**Idea:** {constraints.idea_summary}",
        f"**Persona:** {constraints.target_persona}  |  **Region:** {constraints.region.value}  |  "
        f"**Budget:** ${constraints.budget_usd:,.0f}  |  **Timeline:** {constraints.timeline_weeks} weeks",
        "",
    ]
    for name in orchestrator.WORKER_AGENT_NAMES:
        if name not in outputs:
            continue
        lines.append(f"## {AGENT_DISPLAY_NAMES.get(name, name)}")
        lines.append("")
        lines.append(outputs[name].model_dump_json(indent=2))
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="co-worker", description="100% local, zero-subscription multi-agent co-worker."
    )
    parser.add_argument("idea", help="A natural-language product idea, in quotes.")
    args = parser.parse_args(argv)

    def _confirm_legal_finance(constraints: ProductConstraints, legal_finance_result) -> bool:
        print("\n--- Human checkpoint before releasing Legal/Finance output ---", file=sys.stderr)
        print(legal_finance_result.model_dump_json(indent=2), file=sys.stderr)
        answer = input("Release this Legal/Finance output? [y/N] ").strip().lower()
        return answer == "y"

    try:
        result = run_pipeline(args.idea, checkpoint_fn=_confirm_legal_finance)
    except orchestrator.LegalFinanceCheckpointBlocked:
        print("Run stopped: Legal/Finance output was not approved for release.", file=sys.stderr)
        return 1
    except ModelUnavailableError as exc:
        print(f"Run stopped: {exc}", file=sys.stderr)
        print(
            "Check that Ollama is running locally and the required models are pulled "
            "(see README.md Quick Start / `ollama list`).",
            file=sys.stderr,
        )
        return 1
    except repair_loop.RepairLoopExhausted as exc:
        print(f"Run stopped: {exc}", file=sys.stderr)
        if exc.last_report is not None and exc.last_report.repair_hints is not None:
            print(f"Last failure reason: {exc.last_report.repair_hints.suggested_fix}", file=sys.stderr)
        return 1

    print(result.formatted_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
