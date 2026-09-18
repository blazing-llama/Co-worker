"""TDD tests for src/cli.py: NL input -> orchestrator -> review gate ->
formatted 5-part output. All LLM calls stubbed; runs fully offline.
"""

from __future__ import annotations

import json

import pytest

from src import cli
from src.agents import orchestrator
from src.core.context_manager import ContextManager

RAW_ORCHESTRATOR_PARSE = json.dumps(
    {
        "idea_summary": "A local-first note-taking app for founders.",
        "target_persona": "Solo indie founder",
        "budget_usd": 5000,
        "timeline_weeks": 8,
        "tech_constraints": ["must run offline"],
        "region": "india",
    }
)

RAW_COFOUNDER = json.dumps(
    {
        "tam_usd": 1_000_000,
        "sam_usd": 100_000,
        "unit_economics_summary": "CAC $10, LTV $50",
        "defensibility_notes": "Weak moat",
        "risks": [
            {"category": "value", "description": "d", "severity": "medium"},
            {"category": "usability", "description": "d", "severity": "low"},
            {"category": "feasibility", "description": "d", "severity": "high"},
            {"category": "viability", "description": "d", "severity": "medium"},
        ],
        "verdict_confidence": "medium",
    }
)

RAW_PM = json.dumps(
    {
        "problem_statement": "Founders lack a way to validate ideas cheaply.",
        "user_flows": [{"step_number": 1, "description": "User submits idea"}],
        "requirements": [{"id": "FR-001", "description": "Accept NL input"}],
        "mvp_features": ["CLI input"],
        "post_mvp_features": [],
    }
)

RAW_ENGINEER = json.dumps(
    {
        "architecture_summary": "Hub-and-spoke multi-agent.",
        "data_model_summary": "Pydantic schemas as the wire format.",
        "api_contracts": ["POST /idea"],
        "test_specs": [{"id": "TEST-001", "description": "covers FR-001", "covers_requirement_id": "FR-001"}],
    }
)

RAW_GTM = json.dumps(
    {
        "customer_feedback_themes": [],
        "market_trends": ["Rising demand for local-first tools"],
        "pricing_benchmarks_usd": {"competitor_a": 9.99},
        "channel_strategy": "Reddit + IndieHackers launch",
    }
)

RAW_LEGAL = json.dumps(
    {
        "india_flags": [{"category": "DPDP", "description": "Collects personal data.", "confidence": "medium"}],
        "global_flags": [],
        "ca_cs_lawyer_required": True,
    }
)


def make_fake_chat_fn(raw_response: str):
    def _fake(system_prompt: str, user_prompt: str) -> str:
        return raw_response

    return _fake


def make_rubric_chat_fn(score: float = 0.9):
    def _fake(system_prompt: str, user_prompt: str) -> str:
        return json.dumps({"score": score, "notes": "grounded and complete"})

    return _fake


def make_worker_chat_fns():
    return {
        "cofounder": make_fake_chat_fn(RAW_COFOUNDER),
        "product_manager": make_fake_chat_fn(RAW_PM),
        "engineer": make_fake_chat_fn(RAW_ENGINEER),
        "gtm_ops": make_fake_chat_fn(RAW_GTM),
        "legal_finance": make_fake_chat_fn(RAW_LEGAL),
    }


class TestRunPipeline:
    def test_runs_end_to_end_and_returns_all_five_outputs(self):
        result = cli.run_pipeline(
            "I want a local-first note app for founders.",
            parse_chat_fn=make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE),
            chat_fns=make_worker_chat_fns(),
            review_chat_fn=make_rubric_chat_fn(0.9),
        )
        assert set(result.outputs.keys()) == set(orchestrator.WORKER_AGENT_NAMES)
        for name in orchestrator.WORKER_AGENT_NAMES:
            assert result.reports[name].passed is True

    def test_formatted_output_contains_all_five_sections(self):
        result = cli.run_pipeline(
            "I want a local-first note app for founders.",
            parse_chat_fn=make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE),
            chat_fns=make_worker_chat_fns(),
            review_chat_fn=make_rubric_chat_fn(0.9),
        )
        for heading in ["Co-Founder", "Product", "Engineer", "GTM", "Legal"]:
            assert heading in result.formatted_output

    def test_records_context_entries_for_the_run(self):
        cm = ContextManager(token_threshold=100_000)
        cli.run_pipeline(
            "I want a local-first note app for founders.",
            parse_chat_fn=make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE),
            chat_fns=make_worker_chat_fns(),
            review_chat_fn=make_rubric_chat_fn(0.9),
            context_manager=cm,
        )
        labels = [e.label for e in cm.entries]
        assert "user_prompt" in labels
        assert "constraints" in labels
        assert any(label.startswith("system_reminder:") for label in labels)

    def test_checkpoint_denial_blocks_legal_finance_release(self):
        with pytest.raises(orchestrator.LegalFinanceCheckpointBlocked):
            cli.run_pipeline(
                "I want a local-first note app for founders.",
                parse_chat_fn=make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE),
                chat_fns=make_worker_chat_fns(),
                review_chat_fn=make_rubric_chat_fn(0.9),
                checkpoint_fn=lambda constraints, lf_result: False,
            )

    def test_raises_repair_loop_exhausted_when_review_never_passes(self):
        from src.review.repair_loop import RepairLoopExhausted

        with pytest.raises(RepairLoopExhausted):
            cli.run_pipeline(
                "I want a local-first note app for founders.",
                parse_chat_fn=make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE),
                chat_fns=make_worker_chat_fns(),
                review_chat_fn=make_rubric_chat_fn(0.1),  # always fails rubric
            )


class TestFormatOutput:
    def test_format_output_is_plain_text_not_json_dump(self):
        from src.core.schemas import ProductConstraints, Region

        constraints = ProductConstraints(
            idea_summary="idea",
            target_persona="persona",
            budget_usd=0,
            timeline_weeks=0,
            tech_constraints=[],
            region=Region.INDIA,
        )
        outputs = {}  # empty is fine for this formatting-only check
        text = cli.format_output(constraints, outputs)
        assert "idea" in text
