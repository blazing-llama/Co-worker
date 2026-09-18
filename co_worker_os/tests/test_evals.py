"""TDD tests for src/evals/strands_harness.py. Session-building is pure data
mapping and tested directly; diagnose() takes injectable detect_fn/analyze_fn
so no real LLM-judge call (and no strands-agents-evals network dependency) is
required to pass.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.evals import strands_harness


def make_records():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        strands_harness.AgentCallRecord(
            agent_name="cofounder",
            system_prompt="You are the Co-Founder agent...",
            user_prompt='{"idea_summary": "..."}',
            response='{"tam_usd": 1000000, ...}',
            start_time=start,
            end_time=start + timedelta(seconds=2),
        ),
        strands_harness.AgentCallRecord(
            agent_name="product_manager",
            system_prompt="You are the Product Manager agent...",
            user_prompt='{"idea_summary": "..."}',
            response="not valid json",
            start_time=start + timedelta(seconds=2),
            end_time=start + timedelta(seconds=4),
        ),
    ]


class TestBuildSession:
    def test_builds_session_with_one_span_per_record(self):
        session = strands_harness.build_session("session-123", make_records())
        assert session.session_id == "session-123"
        assert len(session.traces) == 1
        assert len(session.traces[0].spans) == 2

    def test_span_preserves_agent_prompt_and_response(self):
        session = strands_harness.build_session("session-123", make_records())
        first_span = session.traces[0].spans[0]
        assert first_span.user_prompt == '{"idea_summary": "..."}'
        assert "tam_usd" in first_span.agent_response


class TestDiagnose:
    def test_diagnose_invokes_injected_detect_and_analyze_fns(self):
        calls = {"detect": 0, "analyze": 0}

        class FakeFailureOutput:
            failures = ["product_manager returned invalid JSON"]

        class FakeRcaOutput:
            root_causes = ["Model did not follow the JSON-only instruction"]

        def fake_detect_fn(session, **kwargs):
            calls["detect"] += 1
            return FakeFailureOutput()

        def fake_analyze_fn(session, failures=None, **kwargs):
            calls["analyze"] += 1
            return FakeRcaOutput()

        session = strands_harness.build_session("session-123", make_records())
        result = strands_harness.diagnose(session, detect_fn=fake_detect_fn, analyze_fn=fake_analyze_fn)

        assert calls == {"detect": 1, "analyze": 1}
        assert result.failures == ["product_manager returned invalid JSON"]
        assert result.root_causes == ["Model did not follow the JSON-only instruction"]

    def test_diagnose_skips_root_cause_when_no_failures_detected(self):
        calls = {"detect": 0, "analyze": 0}

        class EmptyFailureOutput:
            failures = []

        def fake_detect_fn(session, **kwargs):
            calls["detect"] += 1
            return EmptyFailureOutput()

        def fake_analyze_fn(session, failures=None, **kwargs):
            calls["analyze"] += 1
            raise AssertionError("analyze_fn should not be called when there are no failures")

        session = strands_harness.build_session("session-123", make_records())
        result = strands_harness.diagnose(session, detect_fn=fake_detect_fn, analyze_fn=fake_analyze_fn)

        assert calls == {"detect": 1, "analyze": 0}
        assert result.failures == []
        assert result.root_causes == []


class TestStrandsEvalsAvailability:
    def test_strands_evals_availability_flag_is_boolean(self):
        assert isinstance(strands_harness.STRANDS_EVALS_AVAILABLE, bool)
