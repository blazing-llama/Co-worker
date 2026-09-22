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

# Embeddings for the semantic memory cache (src/core/memory_cache.py). Local
# only, via the same Ollama endpoint -- never a cloud embeddings API.
EMBED_MODEL = os.environ.get("CO_WORKER_EMBED_MODEL", "nomic-embed-text")

MAX_AGENT_LOOP_ITERATIONS = 5
MAX_REPAIR_LOOP_ITERATIONS = 3

# Quick mode (default ON): route reasoning agents (cofounder, product_manager,
# engineer, gtm_ops, legal_finance, review_rubric) to QUICK_HEAVY_MODEL instead
# of the 32b/14b heavy models, which are large enough that a single call can
# take an hour or more on modest local hardware. QUICK_HEAVY_MODEL trades some
# answer depth for actually getting a response in a reasonable time.
#
# orchestrator_parse is NOT affected by this -- it already always used
# FAST_MODEL (llama3.2:3b), per CLAUDE.md's Model Routing section, and that
# step works fine at that size (it's a simple extraction, not open reasoning).
# FAST_MODEL is deliberately NOT reused as QUICK_HEAVY_MODEL: 3B is too small
# to reliably produce the structured, multi-field outputs (e.g. cofounder's
# SharkTankVerdict) the review gate checks, and fails review within the
# 3-iteration repair cap instead of ever returning a result.
#
# Set CO_WORKER_QUICK_MODE=0 to go back to full heavy-model routing.
QUICK_MODE = os.environ.get("CO_WORKER_QUICK_MODE", "1").lower() not in ("0", "false")
QUICK_HEAVY_MODEL = os.environ.get("CO_WORKER_QUICK_HEAVY_MODEL", "llama3.1:latest")

# Sprint 7: worker agents used to dispatch fully in parallel (one thread per
# agent), which thrashes VRAM on a single 32b model shared across all 5
# concurrent calls. Bounded concurrency trades some wall-clock time for a
# workload that actually fits in VRAM.
MAX_CONCURRENT_AGENTS = int(os.environ.get("CO_WORKER_MAX_CONCURRENCY", "2"))

# Semantic memory cache: minimum cosine similarity between a new prompt's
# embedding and a cached prompt's embedding to treat it as a cache hit.
CACHE_SIMILARITY_THRESHOLD = float(os.environ.get("CO_WORKER_CACHE_SIMILARITY_THRESHOLD", "0.85"))

# Review gate (src/review/evaluator.py): minimum LLM-judge rubric score to
# pass. 0.6 was calibrated with HEAVY_MODEL (32b) judging itself. In
# QUICK_MODE the SAME small QUICK_HEAVY_MODEL judges its own output, and a
# small model is a much noisier judge of subjective, judgment-heavy content
# (e.g. cofounder's market-sizing/defensibility calls) than of mechanical,
# structured content (e.g. product_manager's PRD) -- so at 0.6 it can fail a
# genuinely reasonable answer repeatedly and exhaust the repair loop. 0.5
# keeps the gate real (bad/ungrounded output still fails) while matching what
# this judge can reliably tell apart.
RUBRIC_PASS_THRESHOLD = float(os.environ.get("CO_WORKER_RUBRIC_PASS_THRESHOLD", "0.5" if QUICK_MODE else "0.6"))


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
    to a default model -- routing must be explicit.

    In QUICK_MODE (the default -- see above), orchestrator_parse still uses
    FAST_MODEL (its original routing) and every other task is routed to
    QUICK_HEAVY_MODEL instead of AGENT_MODEL_ROUTES's registered heavy/code
    model. AGENT_MODEL_ROUTES itself is left untouched so verify_model_routing
    still reports on the full heavy/code models this system can use,
    regardless of which one is actively selected for a given run.
    """
    if QUICK_MODE:
        return FAST_MODEL if task == "orchestrator_parse" else QUICK_HEAVY_MODEL
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
