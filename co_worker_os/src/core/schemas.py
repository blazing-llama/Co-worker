"""Immutable Pydantic contracts for all inter-agent communication.

Agents never exchange raw free-form text. Every hop between the Orchestrator and a
worker agent, or between a worker and the review gate, is one of these models.
All models are frozen (immutable) so a downstream consumer can never mutate a
contract it was handed.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ConfidenceLevel(str, Enum):
    """Calibration tag required on claims that aren't hard facts."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Region(str, Enum):
    INDIA = "india"
    GLOBAL = "global"


class ProductConstraints(BaseModel):
    """Read-only output of the Orchestrator's NL parse. Every worker agent
    consumes this and only this — never the raw user prompt."""

    model_config = {"frozen": True}

    idea_summary: str = Field(..., min_length=1, description="One-paragraph restatement of the user's idea.")
    target_persona: str = Field(..., min_length=1)
    budget_usd: float = Field(..., ge=0, description="Available budget in USD; 0 means bootstrapped/no budget stated.")
    timeline_weeks: int = Field(..., ge=0)
    tech_constraints: list[str] = Field(default_factory=list)
    region: Region = Region.INDIA

    @model_validator(mode="before")
    @classmethod
    def _default_unstated_numbers_to_zero(cls, data):
        # The orchestrator_parse prompt tells the model to use 0 for an
        # unstated budget/timeline (see orchestrator.PARSE_SYSTEM_PROMPT),
        # but a small/fast model (this step is always routed to FAST_MODEL,
        # see CLAUDE.md's Model Routing section) sometimes emits null
        # instead of following that instruction. Treat null the same as
        # "unstated" here rather than failing validation on a wording choice
        # the prompt already covers semantically.
        if isinstance(data, dict):
            if data.get("budget_usd") is None:
                data["budget_usd"] = 0
            if data.get("timeline_weeks") is None:
                data["timeline_weeks"] = 0
        return data


class ProductRisk(BaseModel):
    model_config = {"frozen": True}

    category: str = Field(..., description="One of: value, usability, feasibility, viability.")
    description: str
    severity: ConfidenceLevel


class SharkTankVerdict(BaseModel):
    """Co-Founder agent output: Shark Tank-style viability assessment."""

    model_config = {"frozen": True}

    tam_usd: float = Field(..., ge=0)
    sam_usd: float = Field(..., ge=0)
    unit_economics_summary: str
    defensibility_notes: str
    risks: list[ProductRisk] = Field(..., min_length=4, max_length=4, description="Exactly 4 risks: value, usability, feasibility, viability.")
    verdict_confidence: ConfidenceLevel

    @model_validator(mode="after")
    def _sam_not_greater_than_tam(self) -> "SharkTankVerdict":
        if self.sam_usd > self.tam_usd:
            raise ValueError("sam_usd cannot exceed tam_usd")
        return self

    @model_validator(mode="after")
    def _covers_all_risk_categories(self) -> "SharkTankVerdict":
        required = {"value", "usability", "feasibility", "viability"}
        present = {r.category.lower() for r in self.risks}
        if present != required:
            raise ValueError(f"risks must cover exactly {required}, got {present}")
        return self


class UserFlowStep(BaseModel):
    model_config = {"frozen": True}

    step_number: int = Field(..., ge=1)
    description: str


class FunctionalRequirement(BaseModel):
    model_config = {"frozen": True}

    id: str = Field(..., pattern=r"^FR-\d{3}$")
    description: str


class PRDSpec(BaseModel):
    """Product Manager agent output."""

    model_config = {"frozen": True}

    problem_statement: str
    user_flows: list[UserFlowStep] = Field(default_factory=list)
    requirements: list[FunctionalRequirement] = Field(..., min_length=1)
    mvp_features: list[str] = Field(..., min_length=1)
    post_mvp_features: list[str] = Field(default_factory=list)


class TestSpec(BaseModel):
    __test__ = False  # not a pytest test class; this is the TEST-XXX contract model

    model_config = {"frozen": True}

    id: str = Field(..., pattern=r"^TEST-\d{3}$")
    description: str
    covers_requirement_id: str = Field(..., pattern=r"^FR-\d{3}$")


class TechStackSpec(BaseModel):
    """Engineering Lead agent output."""

    model_config = {"frozen": True}

    architecture_summary: str
    data_model_summary: str
    api_contracts: list[str] = Field(default_factory=list)
    test_specs: list[TestSpec] = Field(..., min_length=1)


class MarketTheme(BaseModel):
    model_config = {"frozen": True}

    theme: str
    supporting_quote_or_stat: str
    source_url: str
    confidence: ConfidenceLevel


class GTMSentiment(BaseModel):
    """GTM/Research Lead agent output. Every theme must be grounded in a scraper
    source — never invented."""

    model_config = {"frozen": True}

    customer_feedback_themes: list[MarketTheme] = Field(default_factory=list)
    market_trends: list[str] = Field(default_factory=list)
    pricing_benchmarks_usd: dict[str, float] = Field(default_factory=dict)
    channel_strategy: str


class LegalFlag(BaseModel):
    model_config = {"frozen": True}

    category: str = Field(..., description="e.g. DPDP, GST, IT_Act, GDPR, CCPA")
    description: str
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class LegalFlags(BaseModel):
    """Legal/Finance Strategy agent output. See docs/Legal_Finance_Boundaries.md
    for what this agent may and may not assert."""

    model_config = {"frozen": True}

    india_flags: list[LegalFlag] = Field(default_factory=list)
    global_flags: list[LegalFlag] = Field(default_factory=list)
    ca_cs_lawyer_required: bool


class RepairHints(BaseModel):
    model_config = {"frozen": True}

    failed_checks: list[str] = Field(..., min_length=1)
    suggested_fix: str


class ReviewReport(BaseModel):
    """Output of the 2-layer review gate."""

    model_config = {"frozen": True}

    schema_check_passed: bool
    llm_rubric_score: float = Field(..., ge=0.0, le=1.0)
    passed: bool
    repair_hints: RepairHints | None = None

    @model_validator(mode="after")
    def _repair_hints_required_on_fail(self) -> "ReviewReport":
        if not self.passed and self.repair_hints is None:
            raise ValueError("repair_hints is required when passed is False")
        return self
