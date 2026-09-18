"""Ollama endpoint config and model routing. No cloud LLM client lives here."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")

# Heavy reasoning: Shark Tank analysis, PRDs, TDD code generation.
HEAVY_MODEL = os.environ.get("CO_WORKER_HEAVY_MODEL", "qwen2.5:32b")
CODE_MODEL = os.environ.get("CO_WORKER_CODE_MODEL", "qwen2.5-coder:14b")

# Lightweight JSON parsing / routing (Orchestrator's ProductConstraints extraction).
FAST_MODEL = os.environ.get("CO_WORKER_FAST_MODEL", "llama3.2:3b")

MAX_AGENT_LOOP_ITERATIONS = 5
MAX_REPAIR_LOOP_ITERATIONS = 3


@dataclass(frozen=True)
class ModelRoute:
    """Which local model a given task class should use."""

    task: str
    model: str


AGENT_MODEL_ROUTES: dict[str, ModelRoute] = {
    "orchestrator_parse": ModelRoute("orchestrator_parse", FAST_MODEL),
    "cofounder": ModelRoute("cofounder", HEAVY_MODEL),
    "product_manager": ModelRoute("product_manager", HEAVY_MODEL),
    "engineer": ModelRoute("engineer", CODE_MODEL),
    "gtm_ops": ModelRoute("gtm_ops", HEAVY_MODEL),
    "legal_finance": ModelRoute("legal_finance", HEAVY_MODEL),
    "review_rubric": ModelRoute("review_rubric", HEAVY_MODEL),
}


@dataclass(frozen=True)
class OllamaSettings:
    base_url: str = field(default=OLLAMA_BASE_URL)
    api_key: str = field(default="ollama")  # OpenAI-compatible client requires a non-empty value; unused by Ollama.


def get_settings() -> OllamaSettings:
    return OllamaSettings()


def model_for(task: str) -> str:
    """Return the local model name routed for a given task class.

    Raises KeyError for an unregistered task rather than silently falling back
    to a default model — routing must be explicit.
    """
    return AGENT_MODEL_ROUTES[task].model


def list_local_models(http_get=None, base_url: str | None = None) -> list[str]:
    """Query the local Ollama daemon's /api/tags for pulled model names.

    Returns an empty list (never raises) if Ollama isn't reachable — callers
    decide whether that's fatal. `http_get` is injectable for testing.
    """
    import requests

    http_get = http_get or requests.get
    tags_url = (base_url or OLLAMA_BASE_URL).replace("/v1", "") + "/api/tags"
    try:
        response = http_get(tags_url, timeout=5)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []
    return [m.get("name", "") for m in payload.get("models", []) if m.get("name")]


def verify_model_routing(available_models: list[str] | None = None, http_get=None) -> dict[str, bool]:
    """Check each routed model in AGENT_MODEL_ROUTES against what's actually
    pulled locally. Returns {model_name: is_available}. Does not mutate routing
    or silently substitute a model — callers/humans decide what to do with a
    missing model (see docs/STARTING_PROMPTS.md Sprint 3: stop and ask)."""
    available = available_models if available_models is not None else list_local_models(http_get=http_get)
    routed_models = {route.model for route in AGENT_MODEL_ROUTES.values()}
    return {model: model in available for model in routed_models}
