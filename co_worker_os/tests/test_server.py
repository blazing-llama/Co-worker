"""Smoke tests for src/server.py. The real pipeline (run_pipeline) is mocked
via monkeypatch -- this tests HTTP wiring/status codes/response shape, not
agent behavior (that's covered by tests/test_cli.py and friends). No live
Ollama or network call required.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.agents.orchestrator import LegalFinanceCheckpointBlocked
from src.cli import PipelineResult
from src.core.ollama_client import ModelUnavailableError
from src.core.schemas import (
    ConfidenceLevel,
    ProductConstraints,
    ProductRisk,
    Region,
    ReviewReport,
    SharkTankVerdict,
)
from src.evals.strands_harness import AgentCallRecord, DiagnosisResult
from src.review.repair_loop import RepairLoopExhausted
from src.server import app

client = TestClient(app)


def parse_sse_events(raw_text: str) -> list[tuple[str, str]]:
    """Parse raw `event: ...\\ndata: ...\\n\\n` frames into (type, raw_data) pairs."""
    events = []
    for frame in raw_text.split("\n\n"):
        if not frame.strip():
            continue
        lines = frame.strip().split("\n")
        event_type = next(l.split(": ", 1)[1] for l in lines if l.startswith("event: "))
        data = next(l.split(": ", 1)[1] for l in lines if l.startswith("data: "))
        events.append((event_type, data))
    return events


def make_result() -> PipelineResult:
    constraints = ProductConstraints(
        idea_summary="A local-first note app",
        target_persona="Solo founder",
        budget_usd=5000,
        timeline_weeks=8,
        tech_constraints=[],
        region=Region.INDIA,
    )
    verdict = SharkTankVerdict(
        tam_usd=1_000_000,
        sam_usd=100_000,
        unit_economics_summary="x",
        defensibility_notes="x",
        risks=[
            ProductRisk(category="value", description="d", severity=ConfidenceLevel.MEDIUM),
            ProductRisk(category="usability", description="d", severity=ConfidenceLevel.LOW),
            ProductRisk(category="feasibility", description="d", severity=ConfidenceLevel.HIGH),
            ProductRisk(category="viability", description="d", severity=ConfidenceLevel.MEDIUM),
        ],
        verdict_confidence=ConfidenceLevel.MEDIUM,
    )
    report = ReviewReport(schema_check_passed=True, llm_rubric_score=0.9, passed=True)
    return PipelineResult(
        constraints=constraints,
        outputs={"cofounder": verdict},
        reports={"cofounder": report},
        iterations={"cofounder": 1},
        formatted_output="# report",
    )


class TestOllamaStatus:
    def test_returns_disconnected_when_no_models_available(self):
        with patch("src.server.list_local_models", return_value=[]):
            response = client.get("/api/ollama-status")
        assert response.status_code == 200
        body = response.json()
        assert body["connected"] is False
        assert body["available_models"] == []

    def test_returns_connected_with_routing_when_models_present(self):
        with patch("src.server.list_local_models", return_value=["llama3.2:3b"]):
            response = client.get("/api/ollama-status")
        body = response.json()
        assert body["connected"] is True
        assert body["routing"]["llama3.2:3b"] is True


class TestRunTeam:
    def test_returns_200_with_pipeline_result_shape(self):
        with patch("src.server.run_pipeline", return_value=make_result()):
            response = client.post("/api/run-team", json={"prompt": "a local note app"})
        assert response.status_code == 200
        body = response.json()
        assert "cofounder" in body["outputs"]
        assert body["reports"]["cofounder"]["passed"] is True
        assert body["formatted_output"] == "# report"

    def test_returns_502_when_ollama_unavailable(self):
        with patch("src.server.run_pipeline", side_effect=ModelUnavailableError("no ollama")):
            response = client.post("/api/run-team", json={"prompt": "a local note app"})
        assert response.status_code == 502

    def test_returns_422_when_repair_loop_exhausted(self):
        exc = RepairLoopExhausted("gave up", iterations_used=3, last_output=None, last_report=None)
        with patch("src.server.run_pipeline", side_effect=exc):
            response = client.post("/api/run-team", json={"prompt": "a local note app"})
        assert response.status_code == 422

    def test_returns_409_when_legal_finance_checkpoint_blocked(self):
        with patch("src.server.run_pipeline", side_effect=LegalFinanceCheckpointBlocked("blocked")):
            response = client.post("/api/run-team", json={"prompt": "a local note app"})
        assert response.status_code == 409

    def test_rejects_missing_prompt(self):
        response = client.post("/api/run-team", json={})
        assert response.status_code == 422


class TestHealth:
    def test_health_returns_ok(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def make_result_with_call_records() -> PipelineResult:
    result = make_result()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result.call_records = [
        AgentCallRecord(
            agent_name="cofounder:generate",
            system_prompt="sys",
            user_prompt="user",
            response="{}",
            start_time=start,
            end_time=start,
        )
    ]
    return result


class TestRunTeamStream:
    def test_emits_events_from_on_event_and_a_final_result_event(self):
        def fake_run_pipeline(prompt, checkpoint_fn=None, on_event=None, **kwargs):
            on_event("run_start", {"prompt": prompt})
            on_event("agent_start", {"agent": "cofounder"})
            on_event("agent_done", {"agent": "cofounder", "iterations": 1, "passed": True})
            on_event("run_done", {"iterations": {"cofounder": 1}})
            return make_result_with_call_records()

        with patch("src.server.run_pipeline", side_effect=fake_run_pipeline):
            with client.stream("GET", "/api/run-team/stream", params={"prompt": "an idea"}) as response:
                raw = "".join(response.iter_text())

        events = parse_sse_events(raw)
        event_types = [t for t, _ in events]
        assert event_types == ["run_start", "agent_start", "agent_done", "run_done", "result"]

        result_data = json.loads(events[-1][1])
        assert "cofounder" in result_data["outputs"]
        assert len(result_data["call_records"]) == 1

    def test_prefixes_prompt_with_region(self):
        captured = {}

        def fake_run_pipeline(prompt, checkpoint_fn=None, on_event=None, **kwargs):
            captured["prompt"] = prompt
            return make_result_with_call_records()

        with patch("src.server.run_pipeline", side_effect=fake_run_pipeline):
            with client.stream(
                "GET", "/api/run-team/stream", params={"prompt": "an idea", "region": "global"}
            ) as response:
                "".join(response.iter_text())

        assert captured["prompt"].startswith("[region: global]")

    def test_emits_run_error_event_on_model_unavailable(self):
        def fake_run_pipeline(prompt, checkpoint_fn=None, on_event=None, **kwargs):
            raise ModelUnavailableError("no ollama")

        with patch("src.server.run_pipeline", side_effect=fake_run_pipeline):
            with client.stream("GET", "/api/run-team/stream", params={"prompt": "an idea"}) as response:
                raw = "".join(response.iter_text())

        events = parse_sse_events(raw)
        assert events[-1][0] == "run_error"
        error_data = json.loads(events[-1][1])
        assert error_data["reason"] == "model_unavailable"

    def test_a_broken_run_pipeline_never_hangs_the_stream(self):
        def fake_run_pipeline(prompt, checkpoint_fn=None, on_event=None, **kwargs):
            raise RuntimeError("something unexpected")

        with patch("src.server.run_pipeline", side_effect=fake_run_pipeline):
            with client.stream("GET", "/api/run-team/stream", params={"prompt": "an idea"}) as response:
                raw = "".join(response.iter_text())

        events = parse_sse_events(raw)
        assert events[-1][0] == "run_error"
        assert json.loads(events[-1][1])["reason"] == "unexpected"


class TestDiagnose:
    def _request_body(self):
        return {
            "run_id": "run-123",
            "call_records": [
                {
                    "agent_name": "cofounder:generate",
                    "system_prompt": "sys",
                    "user_prompt": "user",
                    "response": "{}",
                    "start_time": "2026-01-01T00:00:00Z",
                    "end_time": "2026-01-01T00:00:01Z",
                }
            ],
        }

    def test_returns_failures_and_root_causes_on_success(self):
        with patch(
            "src.server.diagnose",
            return_value=DiagnosisResult(failures=["cofounder returned malformed JSON"], root_causes=["prompt too vague"]),
        ):
            response = client.post("/api/diagnose", json=self._request_body())

        assert response.status_code == 200
        body = response.json()
        assert body["available"] is True
        assert body["failures"] == ["cofounder returned malformed JSON"]
        assert body["root_causes"] == ["prompt too vague"]

    def test_reports_unavailable_rather_than_fabricating_on_diagnose_failure(self):
        with patch("src.server.diagnose", side_effect=RuntimeError("no local model reachable")):
            response = client.post("/api/diagnose", json=self._request_body())

        assert response.status_code == 200
        body = response.json()
        assert body["available"] is False
        assert "no local model reachable" in body["error"]
        assert body["failures"] == []
        assert body["root_causes"] == []
