import pytest
from pydantic import ValidationError

from src.core.schemas import (
    ConfidenceLevel,
    FunctionalRequirement,
    GTMSentiment,
    LegalFlag,
    LegalFlags,
    PRDSpec,
    ProductConstraints,
    ProductRisk,
    Region,
    RepairHints,
    ReviewReport,
    SharkTankVerdict,
    TechStackSpec,
    TestSpec,
    UserFlowStep,
)


def make_constraints(**overrides) -> ProductConstraints:
    defaults = dict(
        idea_summary="A local-first note-taking app for founders.",
        target_persona="Solo indie founder",
        budget_usd=0,
        timeline_weeks=8,
        tech_constraints=["must run offline"],
        region=Region.INDIA,
    )
    defaults.update(overrides)
    return ProductConstraints(**defaults)


class TestProductConstraints:
    def test_valid_construction(self):
        pc = make_constraints()
        assert pc.region == Region.INDIA

    def test_is_frozen(self):
        pc = make_constraints()
        with pytest.raises(ValidationError):
            pc.budget_usd = 100

    def test_rejects_negative_budget(self):
        with pytest.raises(ValidationError):
            make_constraints(budget_usd=-1)

    def test_null_budget_defaults_to_zero(self):
        # A small/fast model (orchestrator_parse is always routed to
        # FAST_MODEL) may emit null instead of 0 for an unstated budget.
        pc = make_constraints(budget_usd=None)
        assert pc.budget_usd == 0

    def test_null_timeline_weeks_defaults_to_zero(self):
        pc = make_constraints(timeline_weeks=None)
        assert pc.timeline_weeks == 0


class TestSharkTankVerdict:
    def _four_risks(self):
        return [
            ProductRisk(category="value", description="d", severity=ConfidenceLevel.MEDIUM),
            ProductRisk(category="usability", description="d", severity=ConfidenceLevel.LOW),
            ProductRisk(category="feasibility", description="d", severity=ConfidenceLevel.HIGH),
            ProductRisk(category="viability", description="d", severity=ConfidenceLevel.MEDIUM),
        ]

    def test_valid_construction(self):
        verdict = SharkTankVerdict(
            tam_usd=1_000_000,
            sam_usd=100_000,
            unit_economics_summary="CAC $10, LTV $50",
            defensibility_notes="Weak moat, fast follower risk",
            risks=self._four_risks(),
            verdict_confidence=ConfidenceLevel.MEDIUM,
        )
        assert len(verdict.risks) == 4

    def test_rejects_sam_greater_than_tam(self):
        with pytest.raises(ValidationError):
            SharkTankVerdict(
                tam_usd=100,
                sam_usd=1000,
                unit_economics_summary="x",
                defensibility_notes="x",
                risks=self._four_risks(),
                verdict_confidence=ConfidenceLevel.LOW,
            )

    def test_rejects_missing_risk_category(self):
        risks = self._four_risks()[:3]  # drop viability
        risks.append(ProductRisk(category="value", description="dup", severity=ConfidenceLevel.LOW))
        with pytest.raises(ValidationError):
            SharkTankVerdict(
                tam_usd=100,
                sam_usd=50,
                unit_economics_summary="x",
                defensibility_notes="x",
                risks=risks,
                verdict_confidence=ConfidenceLevel.LOW,
            )

    def test_rejects_wrong_risk_count(self):
        with pytest.raises(ValidationError):
            SharkTankVerdict(
                tam_usd=100,
                sam_usd=50,
                unit_economics_summary="x",
                defensibility_notes="x",
                risks=self._four_risks()[:2],
                verdict_confidence=ConfidenceLevel.LOW,
            )


class TestPRDSpec:
    def test_valid_construction(self):
        spec = PRDSpec(
            problem_statement="Founders lack a way to validate ideas cheaply.",
            user_flows=[UserFlowStep(step_number=1, description="User submits idea")],
            requirements=[FunctionalRequirement(id="FR-001", description="Accept NL input")],
            mvp_features=["CLI input"],
        )
        assert spec.requirements[0].id == "FR-001"

    def test_rejects_malformed_requirement_id(self):
        with pytest.raises(ValidationError):
            FunctionalRequirement(id="REQ-1", description="bad id format")

    def test_requires_at_least_one_requirement(self):
        with pytest.raises(ValidationError):
            PRDSpec(
                problem_statement="x",
                requirements=[],
                mvp_features=["x"],
            )


class TestTechStackSpec:
    def test_valid_construction(self):
        spec = TechStackSpec(
            architecture_summary="Hub-and-spoke multi-agent.",
            data_model_summary="Pydantic schemas as the wire format.",
            api_contracts=["POST /idea"],
            test_specs=[TestSpec(id="TEST-001", description="covers FR-001", covers_requirement_id="FR-001")],
        )
        assert spec.test_specs[0].covers_requirement_id == "FR-001"

    def test_rejects_malformed_test_id(self):
        with pytest.raises(ValidationError):
            TestSpec(id="T-1", description="x", covers_requirement_id="FR-001")


class TestGTMSentiment:
    def test_valid_construction_with_grounded_theme(self):
        sentiment = GTMSentiment(
            customer_feedback_themes=[
                {
                    "theme": "Users want offline mode",
                    "supporting_quote_or_stat": "\"I lose data every time wifi drops\" - r/productivity thread",
                    "source_url": "https://reddit.com/r/productivity/example",
                    "confidence": ConfidenceLevel.MEDIUM,
                }
            ],
            market_trends=["Rising demand for local-first tools"],
            pricing_benchmarks_usd={"competitor_a": 9.99},
            channel_strategy="Reddit + IndieHackers launch",
        )
        assert sentiment.customer_feedback_themes[0].source_url.startswith("https://")


class TestLegalFlags:
    def test_valid_construction(self):
        flags = LegalFlags(
            india_flags=[LegalFlag(category="DPDP", description="Collects personal data; DPDP applies.")],
            global_flags=[],
            ca_cs_lawyer_required=True,
        )
        assert flags.ca_cs_lawyer_required is True

    def test_defaults_confidence_to_medium(self):
        flag = LegalFlag(category="GST", description="Revenue-based trigger possible.")
        assert flag.confidence == ConfidenceLevel.MEDIUM


class TestReviewReport:
    def test_passed_report_without_repair_hints(self):
        report = ReviewReport(schema_check_passed=True, llm_rubric_score=0.9, passed=True)
        assert report.repair_hints is None

    def test_failed_report_requires_repair_hints(self):
        with pytest.raises(ValidationError):
            ReviewReport(schema_check_passed=False, llm_rubric_score=0.2, passed=False)

    def test_failed_report_with_repair_hints_is_valid(self):
        report = ReviewReport(
            schema_check_passed=False,
            llm_rubric_score=0.2,
            passed=False,
            repair_hints=RepairHints(failed_checks=["schema"], suggested_fix="Add missing field"),
        )
        assert report.passed is False
