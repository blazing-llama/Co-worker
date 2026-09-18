"""Bounded repair loop: at most MAX_REPAIR_LOOP_ITERATIONS attempts, feeding
RepairHints back to the originating agent between attempts, per CLAUDE.md's
"bounded execution" invariant.
"""

from __future__ import annotations

from typing import Callable, Protocol

from pydantic import BaseModel

from src.core.config import MAX_REPAIR_LOOP_ITERATIONS
from src.core.ollama_client import ChatFn, MalformedAgentOutput
from src.core.schemas import ProductConstraints, RepairHints, ReviewReport
from src.review import evaluator


class RunFn(Protocol):
    def __call__(
        self, constraints: ProductConstraints, chat_fn: ChatFn | None = None, feedback: str | None = None
    ) -> BaseModel: ...


class RepairLoopExhausted(RuntimeError):
    """Raised when max_iterations is reached without a passing ReviewReport.

    Carries the last attempt's output/report so the caller (e.g. the
    orchestrator, or a human reviewing the run) can inspect why it failed
    instead of the failure being silently swallowed.
    """

    def __init__(self, message: str, iterations_used: int, last_output: BaseModel | None, last_report: ReviewReport):
        super().__init__(message)
        self.iterations_used = iterations_used
        self.last_output = last_output
        self.last_report = last_report


def repair_until_passing(
    agent_name: str,
    run_fn: RunFn,
    constraints: ProductConstraints,
    chat_fn: ChatFn | None = None,
    max_iterations: int = MAX_REPAIR_LOOP_ITERATIONS,
    evaluate_kwargs: dict | None = None,
) -> tuple[BaseModel, ReviewReport, int]:
    """Run `run_fn` against `constraints`, review its output, and retry with
    RepairHints feedback up to `max_iterations` times. Returns
    (output, review_report, iterations_used) on success; raises
    RepairLoopExhausted if no attempt passes review within the bound.
    """
    evaluate_kwargs = evaluate_kwargs or {}
    feedback: str | None = None
    last_output: BaseModel | None = None
    last_report: ReviewReport | None = None

    for iteration in range(1, max_iterations + 1):
        try:
            output = run_fn(constraints, chat_fn=chat_fn, feedback=feedback)
        except MalformedAgentOutput as exc:
            feedback = f"Previous output was invalid: {exc}. Return valid JSON matching the required schema."
            last_output = None
            last_report = ReviewReport(
                schema_check_passed=False,
                llm_rubric_score=0.0,
                passed=False,
                repair_hints=RepairHints(failed_checks=["schema"], suggested_fix=feedback),
            )
            continue

        report = evaluator.evaluate(agent_name, output, constraints, chat_fn=chat_fn, **evaluate_kwargs)
        last_output, last_report = output, report

        if report.passed:
            return output, report, iteration

        feedback = report.repair_hints.suggested_fix if report.repair_hints else None

    raise RepairLoopExhausted(
        f"{agent_name} did not pass review within {max_iterations} repair iterations.",
        iterations_used=max_iterations,
        last_output=last_output,
        last_report=last_report,
    )
