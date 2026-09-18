"""Orchestrator: the Hub in the hub-and-spoke pipeline.

Responsibilities, and only these:
1. Parse the user's raw natural-language prompt into an immutable, read-only
   ProductConstraints object (the ONLY place raw user text is ever read).
2. Dispatch that ProductConstraints object concurrently to all 5 worker agents.

Workers never see the raw prompt and never re-parse it — see CLAUDE.md's
schema-first invariant and docs/Architecture.md.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from src.agents import cofounder, engineer, gtm_ops, legal_finance, product_manager
from src.core.config import MAX_CONCURRENT_AGENTS, model_for
from src.core.ollama_client import ChatFn, default_chat_fn, parse_json_response
from src.core.schemas import ProductConstraints

WORKER_AGENT_NAMES: tuple[str, ...] = (
    "cofounder",
    "product_manager",
    "engineer",
    "gtm_ops",
    "legal_finance",
)

_WORKER_RUN_FNS: dict[str, Callable] = {
    "cofounder": cofounder.run,
    "product_manager": product_manager.run,
    "engineer": engineer.run,
    "gtm_ops": gtm_ops.run,
    "legal_finance": legal_finance.run,
}

PARSE_SYSTEM_PROMPT = """\
You are the Orchestrator's parsing stage on a local AI startup team. Given a raw
natural-language product idea from the user, return ONLY a JSON object matching
the ProductConstraints schema: idea_summary, target_persona, budget_usd (number,
0 if unstated), timeline_weeks (integer, 0 if unstated), tech_constraints (list
of strings, may be empty), and region ("india" or "global", default "india" if
unstated). Extract only what the user actually said — never invent a budget,
timeline, or persona the prompt doesn't support. Return raw JSON only, no prose,
no markdown fences.
"""


def parse_constraints(raw_prompt: str, chat_fn: ChatFn | None = None) -> ProductConstraints:
    """The only function in this system that reads a raw user prompt."""
    chat_fn = chat_fn or default_chat_fn(model_for("orchestrator_parse"))
    raw_output = chat_fn(PARSE_SYSTEM_PROMPT, raw_prompt)
    return parse_json_response(raw_output, ProductConstraints)


class LegalFinanceCheckpointBlocked(RuntimeError):
    """Raised when a human-in-the-loop checkpoint_fn declines to release the
    Legal/Finance agent's output (see docs/Architecture.md's human checkpoint
    rule). The agent still ran — its output is withheld from the caller, not
    computed after the fact, mirroring LangGraph's interrupt_before semantics
    (pause before this node's output is exposed downstream)."""


def dispatch(
    constraints: ProductConstraints,
    chat_fns: dict[str, ChatFn] | None = None,
    scraped_context: str | None = None,
    checkpoint_fn: Callable[[ProductConstraints, object], bool] | None = None,
) -> dict[str, object]:
    """Dispatch `constraints` concurrently to all 5 worker agents and return
    {agent_name: parsed_schema_instance}. Workers consume constraints only.

    `chat_fns` maps agent name -> ChatFn; any name omitted falls back to that
    agent's real default (local Ollama model per src/core/config.py routing).
    `scraped_context` (if given) is forwarded only to the gtm_ops agent, which
    is the only worker permitted to ground claims in scraped research.

    `checkpoint_fn`, if given, is called with (constraints, legal_finance_result)
    once all 5 workers have finished, and gates whether the Legal/Finance
    result is released to the caller — the human-in-the-loop checkpoint from
    docs/Architecture.md ("state checkpoint before the Legal/Finance agent ...
    to pause execution for human verification"). If it returns False, `dispatch`
    raises LegalFinanceCheckpointBlocked instead of returning any results.
    Omitting `checkpoint_fn` releases legal_finance unconditionally (e.g. for
    offline testing, or a caller — such as the Sprint 5 CLI — that gates the
    human review step itself before calling dispatch again for final release).
    """
    chat_fns = chat_fns or {}

    def _run_worker(name: str):
        run_fn = _WORKER_RUN_FNS[name]
        chat_fn = chat_fns.get(name)
        if name == "gtm_ops":
            return name, run_fn(constraints, chat_fn=chat_fn, scraped_context=scraped_context)
        return name, run_fn(constraints, chat_fn=chat_fn)

    # Bounded concurrency (see src/core/config.py MAX_CONCURRENT_AGENTS): all 5
    # workers still run without the caller waiting for them one at a time, but
    # at most MAX_CONCURRENT_AGENTS local model calls are ever in flight at
    # once, so they don't all fight over the same GPU's VRAM simultaneously.
    results: dict[str, object] = {}
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_AGENTS) as executor:
        futures = [executor.submit(_run_worker, name) for name in WORKER_AGENT_NAMES]
        for future in futures:
            name, result = future.result()
            results[name] = result

    if checkpoint_fn is not None and not checkpoint_fn(constraints, results["legal_finance"]):
        raise LegalFinanceCheckpointBlocked(
            "Human-in-the-loop checkpoint declined to release the Legal/Finance agent's output."
        )

    return results
