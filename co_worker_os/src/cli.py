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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from src.agents import orchestrator
from src.core.context_manager import ContextManager
from src.core.ollama_client import ChatFn, ModelUnavailableError
from src.core.schemas import ProductConstraints, ReviewReport
from src.review import repair_loop

AGENT_DISPLAY_NAMES: dict[str, str] = {
    "cofounder": "Co-Founder (Shark Tank Verdict)",
    "product_manager": "Product Manager (PRD)",
    "engineer": "Engineering Lead (Tech Stack)",
    "gtm_ops": "GTM & Research (Market Sentiment)",
    "legal_finance": "Legal/Finance (Compliance Flags)",
}


@dataclass
class PipelineResult:
    constraints: ProductConstraints
    outputs: dict[str, object] = field(default_factory=dict)
    reports: dict[str, ReviewReport] = field(default_factory=dict)
    iterations: dict[str, int] = field(default_factory=dict)
    formatted_output: str = ""


def run_pipeline(
    raw_prompt: str,
    parse_chat_fn: ChatFn | None = None,
    chat_fns: dict[str, ChatFn] | None = None,
    review_chat_fn: ChatFn | None = None,
    scraped_context: str | None = None,
    checkpoint_fn: Callable[[ProductConstraints, object], bool] | None = None,
    context_manager: ContextManager | None = None,
    max_repair_iterations: int = 3,
) -> PipelineResult:
    """Run the full local pipeline for one natural-language idea prompt.

    Every worker's output is review-gated (Sprint 4's 2-layer gate + bounded
    repair loop) before being included in the result -- a malformed or
    ungrounded output never reaches `formatted_output` silently; it either
    gets repaired within `max_repair_iterations` or `RepairLoopExhausted`
    propagates to the caller.
    """
    chat_fns = chat_fns or {}
    context_manager = context_manager or ContextManager()

    context_manager.add_entry("user_prompt", raw_prompt)
    constraints = orchestrator.parse_constraints(raw_prompt, chat_fn=parse_chat_fn)
    context_manager.add_entry("constraints", constraints.model_dump_json())

    def _run_fn_for(name: str):
        # repair_loop.repair_until_passing calls run_fn(constraints, chat_fn=..., feedback=...)
        # using the SAME chat_fn it passes to evaluator.evaluate() for the rubric judge.
        # Workers and the rubric judge need different chat_fns (a worker's raw JSON output
        # is not a valid RubricScore), so this wrapper ignores the incoming chat_fn and
        # always uses this agent's own worker_chat_fn -- the rubric's chat_fn is supplied
        # separately as `review_chat_fn` below.
        base_run_fn = orchestrator._WORKER_RUN_FNS[name]
        worker_chat_fn = chat_fns.get(name)

        def _wrapped(constraints: ProductConstraints, chat_fn: ChatFn | None = None, feedback: str | None = None):
            if name == "gtm_ops":
                return base_run_fn(
                    constraints, chat_fn=worker_chat_fn, scraped_context=scraped_context, feedback=feedback
                )
            return base_run_fn(constraints, chat_fn=worker_chat_fn, feedback=feedback)

        return _wrapped

    def _repair_one(name: str):
        context_manager.build_dispatch_reminder(name)
        output, report, iterations = repair_loop.repair_until_passing(
            name,
            _run_fn_for(name),
            constraints,
            chat_fn=review_chat_fn,
            max_iterations=max_repair_iterations,
        )
        context_manager.add_entry(name, output.model_dump_json())
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

    if checkpoint_fn is not None and not checkpoint_fn(constraints, outputs["legal_finance"]):
        raise orchestrator.LegalFinanceCheckpointBlocked(
            "Human-in-the-loop checkpoint declined to release the Legal/Finance agent's output."
        )

    formatted_output = format_output(constraints, outputs)
    return PipelineResult(
        constraints=constraints,
        outputs=outputs,
        reports=reports,
        iterations=iterations,
        formatted_output=formatted_output,
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
