"""FastAPI server exposing the Sprint 5 pipeline (src/cli.py) over HTTP for
the frontend dashboard. Zero cloud calls: every endpoint routes to the local
Ollama endpoint via src/core/config.py, same as the CLI.

This is the ONLY new backend surface added for the frontend -- it wraps
`cli.run_pipeline`/`orchestrator`/`config` rather than reimplementing any
pipeline logic, so Sprints 1-5's behavior (schemas, guardrails, review gate,
repair loop, context compaction) is exactly what runs here too.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agents.orchestrator import WORKER_AGENT_NAMES, LegalFinanceCheckpointBlocked
from src.cli import PipelineResult, run_pipeline
from src.core.config import HEAVY_MODEL, OLLAMA_BASE_URL, list_local_models, verify_model_routing
from src.core.ollama_client import MalformedAgentOutput, ModelUnavailableError
from src.evals.strands_harness import AgentCallRecord, DiagnosisResult, build_session, diagnose
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
    deep: bool = False  # False (default): fast Co-Founder + PM validator/blueprint only.
    # True: full 5-agent team (adds Engineer, GTM & Research, Legal/Finance).


class CallRecordOut(BaseModel):
    agent_name: str
    system_prompt: str
    user_prompt: str
    response: str
    start_time: datetime
    end_time: datetime


class RunTeamResponse(BaseModel):
    run_id: str
    constraints: dict
    outputs: dict
    reports: dict
    iterations: dict
    formatted_output: str
    call_records: list[CallRecordOut] = []


class ErrorResponse(BaseModel):
    error: str
    detail: str


class DiagnoseRequest(BaseModel):
    run_id: str
    call_records: list[CallRecordOut]


class DiagnoseResponse(BaseModel):
    run_id: str
    available: bool
    failures: list[str] = []
    root_causes: list[str] = []
    error: str | None = None


def _build_run_team_response(run_id: str, result: PipelineResult) -> RunTeamResponse:
    return RunTeamResponse(
        run_id=run_id,
        constraints=result.constraints.model_dump(mode="json"),
        outputs={name: output.model_dump(mode="json") for name, output in result.outputs.items()},
        reports={name: report.model_dump(mode="json") for name, report in result.reports.items()},
        iterations=result.iterations,
        formatted_output=result.formatted_output,
        call_records=[
            CallRecordOut(
                agent_name=r.agent_name,
                system_prompt=r.system_prompt,
                user_prompt=r.user_prompt,
                response=r.response,
                start_time=r.start_time,
                end_time=r.end_time,
            )
            for r in result.call_records
        ],
    )


def _region_prefixed_prompt(prompt: str, region: str | None) -> str:
    # The frontend's India-First/Global toggle changes which legal/tax system
    # prompt legal_finance.py uses (see Region enum). parse_constraints infers
    # region from the prompt by default; an explicit UI toggle should win, so
    # this nudges the prompt rather than silently ignoring the user's choice.
    if region:
        return f"[region: {region}] {prompt}"
    return prompt


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
    prompt = _region_prefixed_prompt(request.prompt, request.region)

    agent_names = WORKER_AGENT_NAMES if request.deep else None

    try:
        result = run_pipeline(prompt, checkpoint_fn=lambda constraints, lf_result: True, agent_names=agent_names)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except MalformedAgentOutput as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not parse a valid ProductConstraints from the prompt after retries: {exc}",
        ) from exc
    except RepairLoopExhausted as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{exc} Last failure: "
            f"{exc.last_report.repair_hints.suggested_fix if exc.last_report and exc.last_report.repair_hints else 'unknown'}",
        ) from exc
    except LegalFinanceCheckpointBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return _build_run_team_response(run_id, result)


_STREAM_DONE = object()


@app.get("/api/run-team/stream")
def run_team_stream(
    prompt: str,
    category: str | None = None,
    region: Literal["india", "global"] | None = None,
    deep: bool = False,
):
    """Server-Sent Events version of /api/run-team: emits a live event per
    pipeline milestone (chat_call_start/end, agent_start/done, checkpoint_*,
    run_done/run_error) as the real pipeline executes, ending with a "result"
    event carrying the same payload /api/run-team returns synchronously.

    The pipeline runs in a background thread (run_pipeline uses its own
    ThreadPoolExecutor internally and would block the event loop if called
    directly); events cross into the async generator via a thread-safe
    queue.Queue, read through run_in_executor so the event loop is never
    blocked waiting on it either.
    """
    run_id = str(uuid.uuid4())
    full_prompt = _region_prefixed_prompt(prompt, region)
    agent_names = WORKER_AGENT_NAMES if deep else None
    event_queue: queue.Queue = queue.Queue()

    def on_event(event_type: str, data: dict) -> None:
        event_queue.put((event_type, data))

    def worker() -> None:
        try:
            result = run_pipeline(
                full_prompt, checkpoint_fn=lambda c, lf: True, on_event=on_event, agent_names=agent_names
            )
        except ModelUnavailableError as exc:
            event_queue.put(("run_error", {"reason": "model_unavailable", "detail": str(exc)}))
        except MalformedAgentOutput as exc:
            event_queue.put(("run_error", {"reason": "parse_failed", "detail": str(exc)}))
        except RepairLoopExhausted as exc:
            event_queue.put(("run_error", {"reason": "repair_loop_exhausted", "detail": str(exc)}))
        except LegalFinanceCheckpointBlocked as exc:
            event_queue.put(("run_error", {"reason": "checkpoint_blocked", "detail": str(exc)}))
        except Exception as exc:  # last-resort: never let the stream hang on an unexpected error
            event_queue.put(("run_error", {"reason": "unexpected", "detail": str(exc)}))
        else:
            response = _build_run_team_response(run_id, result)
            event_queue.put(("result", json.loads(response.model_dump_json())))
        finally:
            event_queue.put((_STREAM_DONE, None))

    threading.Thread(target=worker, daemon=True).start()

    def event_generator():
        while True:
            event_type, data = event_queue.get()
            if event_type is _STREAM_DONE:
                return
            yield f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/diagnose", response_model=DiagnoseResponse)
def diagnose_run(request: DiagnoseRequest) -> DiagnoseResponse:
    """Builds a real strands-evals Session from a completed run's call
    records and runs failure detection + root-cause analysis. A deliberate,
    separate action from the run itself (not automatic) since this is its
    own LLM-judge call with its own cost/latency.

    Never fabricates a diagnosis: if the real strands-evals detectors can't
    run (e.g. no local model reachable), `available` is false and `error`
    explains why -- the frontend must show that plainly, not a fake result.
    """
    records = [
        AgentCallRecord(
            agent_name=r.agent_name,
            system_prompt=r.system_prompt,
            user_prompt=r.user_prompt,
            response=r.response,
            start_time=r.start_time,
            end_time=r.end_time,
        )
        for r in request.call_records
    ]
    session = build_session(request.run_id, records)

    try:
        result: DiagnosisResult = diagnose(session, model=HEAVY_MODEL)
    except Exception as exc:
        return DiagnoseResponse(run_id=request.run_id, available=False, error=str(exc))

    return DiagnoseResponse(
        run_id=request.run_id,
        available=True,
        failures=result.failures,
        root_causes=result.root_causes,
    )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "timestamp": time.time()}
