"""2-layer review gate.

Layer 1 (programmatic): the output already passed Pydantic structural
validation by the time it reaches here (agents raise MalformedAgentOutput
before returning anything else); this layer adds the cross-field/cross-agent
checks Pydantic can't express alone — coverage completeness and budget sanity.

Layer 2 (LLM rubric): a local-model judge scores qualitative grounding and
constraint adherence, via an AG2-style single-reviewer call (a full AG2
group-chat cross-review across agents is a Sprint 4 stretch goal, not required
for this gate to function — see docs/ImplementationPlan.md).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.core.ollama_client import ChatFn, default_chat_fn, parse_json_response
from src.core.config import RUBRIC_PASS_THRESHOLD, model_for
from src.core.schemas import (
    PRDSpec,
    ProductConstraints,
    RepairHints,
    ReviewReport,
    SharkTankVerdict,
    TechStackSpec,
)


class RubricScore(BaseModel):
    """Layer 2 LLM judge output. Internal to the review gate — not one of the
    6 inter-agent contracts, since it's produced by the reviewer, not a worker."""

    score: float = Field(..., ge=0.0, le=1.0)
    notes: str


RUBRIC_SYSTEM_PROMPT = """\
You are the Review Gate's rubric judge on a local AI startup team. Given an
agent's name, its output (as JSON), and the ProductConstraints it was asked to
satisfy, score how well the output is: (1) grounded in the given constraints
and any supplied scraped context, not invented; (2) consistent with the stated
budget, timeline, region, and tech constraints; (3) qualitatively complete for
its role. Return ONLY a JSON object: {"score": <float 0.0-1.0>, "notes":
"<one paragraph explaining the score, calling out anything ungrounded>"}.
Return raw JSON only, no prose, no markdown fences.
"""


def check_requirement_coverage(prd: PRDSpec, tech: TechStackSpec) -> list[str]:
    """Every FR-XXX in the PRD must be covered by at least one TEST-XXX in the
    tech spec. Returns a list of human-readable failure messages (empty if
    fully covered)."""
    covered_fr_ids = {test.covers_requirement_id for test in tech.test_specs}
    failures = []
    for requirement in prd.requirements:
        if requirement.id not in covered_fr_ids:
            failures.append(f"{requirement.id} has no covering TEST-XXX in TechStackSpec.test_specs")
    return failures


def check_budget_sanity(constraints: ProductConstraints, verdict: SharkTankVerdict) -> list[str]:
    """A TAM smaller than the founder's stated budget is not directionally
    sane -- flag it rather than silently pass a self-contradictory verdict."""
    failures = []
    if constraints.budget_usd > 0 and verdict.tam_usd < constraints.budget_usd:
        failures.append(
            f"tam_usd ({verdict.tam_usd}) is smaller than the stated budget_usd "
            f"({constraints.budget_usd}) -- market sizing looks inconsistent with the constraints."
        )
    return failures


def llm_rubric_score(
    agent_name: str,
    output: BaseModel,
    constraints: ProductConstraints,
    chat_fn: ChatFn | None = None,
    scraped_context: str | None = None,
) -> RubricScore:
    chat_fn = chat_fn or default_chat_fn(model_for("review_rubric"))
    user_prompt = (
        f"agent_name: {agent_name}\n"
        f"constraints: {constraints.model_dump_json()}\n"
        f"agent_output: {output.model_dump_json()}"
    )
    if scraped_context:
        user_prompt += f"\nscraped_context: {scraped_context}"
    raw_output = chat_fn(RUBRIC_SYSTEM_PROMPT, user_prompt)
    return parse_json_response(raw_output, RubricScore)


def evaluate(
    agent_name: str,
    output: BaseModel,
    constraints: ProductConstraints,
    chat_fn: ChatFn | None = None,
    extra_checks: list[str] | None = None,
    scraped_context: str | None = None,
    rubric_threshold: float = RUBRIC_PASS_THRESHOLD,
) -> ReviewReport:
    """Run both review layers and return one ReviewReport.

    `extra_checks` is the caller-computed Layer 1 cross-agent/cross-field
    failure list (e.g. `check_requirement_coverage(...) + check_budget_sanity(...)`)
    -- this function stays agent-agnostic; callers supply the checks relevant
    to the agent being reviewed.
    """
    layer1_failures = list(extra_checks or [])
    schema_check_passed = not layer1_failures

    rubric = llm_rubric_score(agent_name, output, constraints, chat_fn=chat_fn, scraped_context=scraped_context)
    rubric_passed = rubric.score >= rubric_threshold

    passed = schema_check_passed and rubric_passed

    repair_hints = None
    if not passed:
        failed_checks = list(layer1_failures)
        if not rubric_passed:
            failed_checks.append(f"llm_rubric_score {rubric.score:.2f} below threshold {rubric_threshold}")
        repair_hints = RepairHints(
            failed_checks=failed_checks,
            suggested_fix=rubric.notes if not rubric_passed else "; ".join(layer1_failures),
        )

    return ReviewReport(
        schema_check_passed=schema_check_passed,
        llm_rubric_score=rubric.score,
        passed=passed,
        repair_hints=repair_hints,
    )
