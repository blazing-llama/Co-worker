"""Smoke tests for src/server.py. The real pipeline (run_pipeline) is mocked
via monkeypatch -- this tests HTTP wiring/status codes/response shape, not
agent behavior (that's covered by tests/test_cli.py and friends). No live
Ollama or network call required.
"""

from __future__ import annotations

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
from src.review.repair_loop import RepairLoopExhausted
from src.server import app

client = TestClient(app)


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
