"""TDD tests for src/review/ (2-layer review gate + bounded repair loop). All
LLM calls stubbed; runs fully offline.
"""

from __future__ import annotations

import json

import pytest

from src.core.ollama_client import MalformedAgentOutput
from src.core.schemas import (
    ConfidenceLevel,
    FunctionalRequirement,
    PRDSpec,
    ProductConstraints,
    ProductRisk,
    Region,
    SharkTankVerdict,
    TechStackSpec,
    TestSpec,
    UserFlowStep,
)
from src.review import evaluator, repair_loop

CONSTRAINTS = ProductConstraints(
    idea_summary="A local-first note-taking app for founders.",
    target_persona="Solo indie founder",
    budget_usd=5000,
    timeline_weeks=8,
    tech_constraints=["must run offline"],
    region=Region.INDIA,
)


def make_verdict(tam_usd=1_000_000, sam_usd=100_000) -> SharkTankVerdict:
    return SharkTankVerdict(
        tam_usd=tam_usd,
        sam_usd=sam_usd,
        unit_economics_summary="CAC $10, LTV $50",
        defensibility_notes="Weak moat",
        risks=[
            ProductRisk(category="value", description="d", severity=ConfidenceLevel.MEDIUM),
            ProductRisk(category="usability", description="d", severity=ConfidenceLevel.LOW),
            ProductRisk(category="feasibility", description="d", severity=ConfidenceLevel.HIGH),
            ProductRisk(category="viability", description="d", severity=ConfidenceLevel.MEDIUM),
        ],
        verdict_confidence=ConfidenceLevel.MEDIUM,
    )


def make_prd(fr_ids=("FR-001",)) -> PRDSpec:
    return PRDSpec(
        problem_statement="Founders lack a cheap way to validate ideas.",
        user_flows=[UserFlowStep(step_number=1, description="Submit idea")],
        requirements=[FunctionalRequirement(id=fr_id, description="req") for fr_id in fr_ids],
        mvp_features=["CLI input"],
    )


def make_tech(covers=("FR-001",)) -> TechStackSpec:
    return TechStackSpec(
        architecture_summary="Hub-and-spoke.",
        data_model_summary="Pydantic schemas.",
        api_contracts=["POST /idea"],
        test_specs=[
            TestSpec(id=f"TEST-{i + 1:03d}", description="covers", covers_requirement_id=fr_id)
            for i, fr_id in enumerate(covers)
        ],
    )


def rubric_chat_fn(score: float, notes: str = "looks fine"):
    def _fake(system_prompt: str, user_prompt: str) -> str:
        return json.dumps({"score": score, "notes": notes})

    return _fake


# --- Layer 1: programmatic checks ------------------------------------------


class TestLayer1RequirementCoverage:
    def test_full_coverage_returns_no_failures(self):
        prd = make_prd(fr_ids=("FR-001", "FR-002"))
        tech = make_tech(covers=("FR-001", "FR-002"))
        assert evaluator.check_requirement_coverage(prd, tech) == []

    def test_uncovered_requirement_is_reported(self):
        prd = make_prd(fr_ids=("FR-001", "FR-002"))
        tech = make_tech(covers=("FR-001",))
        failures = evaluator.check_requirement_coverage(prd, tech)
        assert any("FR-002" in f for f in failures)


class TestLayer1BudgetSanity:
    def test_tam_below_stated_budget_is_flagged(self):
        verdict = make_verdict(tam_usd=100, sam_usd=50)
        failures = evaluator.check_budget_sanity(CONSTRAINTS, verdict)
        assert failures  # CONSTRAINTS.budget_usd = 5000 > tam_usd = 100

    def test_tam_above_budget_passes(self):
        verdict = make_verdict(tam_usd=1_000_000, sam_usd=100_000)
        assert evaluator.check_budget_sanity(CONSTRAINTS, verdict) == []


# --- Layer 2: LLM rubric ----------------------------------------------------


class TestLayer2Rubric:
    def test_parses_valid_rubric_response(self):
        chat_fn = rubric_chat_fn(score=0.85, notes="well grounded")
        result = evaluator.llm_rubric_score("cofounder", make_verdict(), CONSTRAINTS, chat_fn=chat_fn)
        assert result.score == 0.85
        assert result.notes == "well grounded"

    def test_raises_on_out_of_range_score(self):
        chat_fn = rubric_chat_fn(score=1.5)
        with pytest.raises(MalformedAgentOutput):
            evaluator.llm_rubric_score("cofounder", make_verdict(), CONSTRAINTS, chat_fn=chat_fn)


# --- evaluate(): full gate ---------------------------------------------------


class TestEvaluate:
    def test_passes_when_layer1_clean_and_rubric_above_threshold(self):
        chat_fn = rubric_chat_fn(score=0.9)
        report = evaluator.evaluate("cofounder", make_verdict(), CONSTRAINTS, chat_fn=chat_fn)
        assert report.passed is True
        assert report.schema_check_passed is True
        assert report.repair_hints is None

    def test_fails_when_rubric_below_threshold(self):
        chat_fn = rubric_chat_fn(score=0.2, notes="ungrounded market claims")
        report = evaluator.evaluate("cofounder", make_verdict(), CONSTRAINTS, chat_fn=chat_fn)
        assert report.passed is False
        assert report.repair_hints is not None
        assert "ungrounded market claims" in report.repair_hints.suggested_fix

    def test_fails_on_extra_check_failures(self):
        chat_fn = rubric_chat_fn(score=0.9)
        report = evaluator.evaluate(
            "cofounder",
            make_verdict(tam_usd=100, sam_usd=50),
            CONSTRAINTS,
            chat_fn=chat_fn,
            extra_checks=evaluator.check_budget_sanity(CONSTRAINTS, make_verdict(tam_usd=100, sam_usd=50)),
        )
        assert report.passed is False
        assert report.schema_check_passed is False


# --- Bounded repair loop -----------------------------------------------------


class TestRepairLoop:
    def test_succeeds_first_try_when_output_passes_review(self):
        def run_fn(constraints, chat_fn=None, feedback=None):
            return make_verdict()

        output, report, iterations = repair_loop.repair_until_passing(
            "cofounder", run_fn, CONSTRAINTS, chat_fn=rubric_chat_fn(score=0.9), max_iterations=3
        )
        assert iterations == 1
        assert report.passed is True

    def test_retries_on_malformed_output_then_succeeds(self):
        attempts = {"count": 0}

        def run_fn(constraints, chat_fn=None, feedback=None):
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise MalformedAgentOutput("bad json", raw_output="not json")
            return make_verdict()

        output, report, iterations = repair_loop.repair_until_passing(
            "cofounder", run_fn, CONSTRAINTS, chat_fn=rubric_chat_fn(score=0.9), max_iterations=3
        )
        assert iterations == 2
        assert report.passed is True

    def test_passes_repair_hints_back_to_agent_on_rubric_failure(self):
        received_feedback = []

        def run_fn(constraints, chat_fn=None, feedback=None):
            received_feedback.append(feedback)
            return make_verdict()

        scores = iter([0.2, 0.9])  # fails first review, passes second

        def scored_rubric_chat_fn(system_prompt, user_prompt):
            return json.dumps({"score": next(scores), "notes": "needs more grounding"})

        output, report, iterations = repair_loop.repair_until_passing(
            "cofounder", run_fn, CONSTRAINTS, chat_fn=scored_rubric_chat_fn, max_iterations=3
        )

        assert iterations == 2
        assert report.passed is True
        assert received_feedback[0] is None  # first attempt: no feedback yet
        assert received_feedback[1] is not None
        assert "needs more grounding" in received_feedback[1]

    def test_raises_repair_loop_exhausted_after_max_iterations(self):
        def run_fn(constraints, chat_fn=None, feedback=None):
            return make_verdict()

        chat_fn = rubric_chat_fn(score=0.1, notes="never good enough")

        with pytest.raises(repair_loop.RepairLoopExhausted) as exc_info:
            repair_loop.repair_until_passing("cofounder", run_fn, CONSTRAINTS, chat_fn=chat_fn, max_iterations=3)

        assert exc_info.value.iterations_used == 3
        assert exc_info.value.last_report.passed is False

    def test_never_exceeds_max_iterations_even_with_persistent_malformed_output(self):
        def run_fn(constraints, chat_fn=None, feedback=None):
            raise MalformedAgentOutput("always bad", raw_output="still not json")

        with pytest.raises(repair_loop.RepairLoopExhausted) as exc_info:
            repair_loop.repair_until_passing(
                "cofounder", run_fn, CONSTRAINTS, chat_fn=rubric_chat_fn(score=0.9), max_iterations=3
            )
        assert exc_info.value.iterations_used == 3
