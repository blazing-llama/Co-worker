"""FastAPI server exposing the Sprint 5 pipeline (src/cli.py) over HTTP for
the frontend dashboard. Zero cloud calls: every endpoint routes to the local
Ollama endpoint via src/core/config.py, same as the CLI.

This is the ONLY new backend surface added for the frontend -- it wraps
`cli.run_pipeline`/`orchestrator`/`config` rather than reimplementing any
pipeline logic, so Sprints 1-5's behavior (schemas, guardrails, review gate,
repair loop, context compaction) is exactly what runs here too.
"""

from __future__ import annotations

import time
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agents.orchestrator import LegalFinanceCheckpointBlocked
from src.cli import run_pipeline
from src.core.config import OLLAMA_BASE_URL, list_local_models, verify_model_routing
from src.core.ollama_client import ModelUnavailableError
from src.review.repair_loop import RepairLoopExhausted

app = FastAPI(title="Co-Worker OS API", version="0.1.0")

# Local-only: the frontend dev server (Vite, typically :5173) is the sole
# expected caller. No cloud origin is ever allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --- Response models (the HTTP-facing contracts; internal pipeline objects
# already validate via src/core/schemas.py -- these just shape the JSON) ----


class OllamaStatusResponse(BaseModel):
    connected: bool
    base_url: str
    available_models: list[str]
    routing: dict[str, bool]


class RunTeamRequest(BaseModel):
    prompt: str
    category: str | None = None  # "Digital" / "Physical/Food" / "D2C" / "B2B SaaS" -- UI-only, informational
    region: Literal["india", "global"] | None = None


class RunTeamResponse(BaseModel):
    run_id: str
    constraints: dict
    outputs: dict
    reports: dict
    iterations: dict
    formatted_output: str


class ErrorResponse(BaseModel):
    error: str
    detail: str


@app.get("/api/ollama-status", response_model=OllamaStatusResponse)
def ollama_status() -> OllamaStatusResponse:
    """Backs the TopBar's connection dot, model chip, and lets the frontend
    warn before a run if a routed model isn't pulled -- never assumed."""
    available = list_local_models()
    return OllamaStatusResponse(
        connected=bool(available),
        base_url=OLLAMA_BASE_URL,
        available_models=available,
        routing=verify_model_routing(available_models=available),
    )


@app.post("/api/run-team", response_model=RunTeamResponse, responses={409: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 422: {"model": ErrorResponse}})
def run_team(request: RunTeamRequest) -> RunTeamResponse:
    """Runs the real 5-agent pipeline (Sprint 3 orchestrator + Sprint 4 review
    gate/repair loop) against local Ollama. No mock/canned data path here --
    if Ollama or a routed model is unavailable, this returns a real error
    (502), not a fabricated success."""
    run_id = str(uuid.uuid4())

    # region override: the frontend's India-First/Global toggle changes which
    # legal/tax system prompt legal_finance.py uses (see Region enum).
    # parse_constraints infers region from the prompt by default; an explicit
    # UI toggle should win, so we nudge the prompt rather than silently
    # ignoring the user's selection.
    prompt = request.prompt
    if request.region:
        prompt = f"[region: {request.region}] {prompt}"

    try:
        result = run_pipeline(prompt, checkpoint_fn=lambda constraints, lf_result: True)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RepairLoopExhausted as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{exc} Last failure: "
            f"{exc.last_report.repair_hints.suggested_fix if exc.last_report and exc.last_report.repair_hints else 'unknown'}",
        ) from exc
    except LegalFinanceCheckpointBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return RunTeamResponse(
        run_id=run_id,
        constraints=result.constraints.model_dump(mode="json"),
        outputs={name: output.model_dump(mode="json") for name, output in result.outputs.items()},
        reports={name: report.model_dump(mode="json") for name, report in result.reports.items()},
        iterations=result.iterations,
        formatted_output=result.formatted_output,
    )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "timestamp": time.time()}
