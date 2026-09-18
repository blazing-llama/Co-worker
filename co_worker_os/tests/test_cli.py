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

    def test_captures_call_records_for_every_real_chat_fn_call(self):
        result = cli.run_pipeline(
            "I want a local-first note app for founders.",
            parse_chat_fn=make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE),
            chat_fns=make_worker_chat_fns(),
            review_chat_fn=make_rubric_chat_fn(0.9),
        )
        agent_role_pairs = {(r.agent_name.split(":")[0], r.agent_name.split(":")[1]) for r in result.call_records}
        # 1 orchestrator parse call + (1 generate + 1 review) per worker agent.
        assert ("orchestrator", "parse") in agent_role_pairs
        for name in orchestrator.WORKER_AGENT_NAMES:
            assert (name, "generate") in agent_role_pairs
            assert (name, "review") in agent_role_pairs
        assert len(result.call_records) == 1 + 2 * len(orchestrator.WORKER_AGENT_NAMES)

    def test_call_records_preserve_real_prompts_and_responses(self):
        result = cli.run_pipeline(
            "I want a local-first note app for founders.",
            parse_chat_fn=make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE),
            chat_fns=make_worker_chat_fns(),
            review_chat_fn=make_rubric_chat_fn(0.9),
        )
        cofounder_call = next(r for r in result.call_records if r.agent_name == "cofounder:generate")
        assert cofounder_call.response == RAW_COFOUNDER
        assert cofounder_call.start_time <= cofounder_call.end_time

    def test_emits_events_in_expected_order_on_success(self):
        events: list[tuple[str, dict]] = []
        cli.run_pipeline(
            "I want a local-first note app for founders.",
            parse_chat_fn=make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE),
            chat_fns=make_worker_chat_fns(),
            review_chat_fn=make_rubric_chat_fn(0.9),
            on_event=lambda t, d: events.append((t, d)),
        )
        event_types = [t for t, _ in events]
        assert event_types[0] == "run_start"
        assert "parse_start" in event_types
        assert "parse_done" in event_types
        assert event_types[-1] == "run_done"
        # Every agent that ran must report agent_start before agent_done.
        for name in orchestrator.WORKER_AGENT_NAMES:
            start_idx = event_types.index("agent_start")
            done_events = [d for t, d in events if t == "agent_done" and d.get("agent") == name]
            assert len(done_events) == 1
            assert done_events[0]["passed"] is True
            assert start_idx < event_types.index("agent_done")

    def test_emits_agent_failed_event_when_repair_loop_exhausted(self):
        from src.review.repair_loop import RepairLoopExhausted

        events: list[tuple[str, dict]] = []
        with pytest.raises(RepairLoopExhausted):
            cli.run_pipeline(
                "I want a local-first note app for founders.",
                parse_chat_fn=make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE),
                chat_fns=make_worker_chat_fns(),
                review_chat_fn=make_rubric_chat_fn(0.1),
                on_event=lambda t, d: events.append((t, d)),
            )
        assert any(t == "agent_failed" for t, _ in events)

    def test_emits_checkpoint_events_and_run_error_on_denial(self):
        events: list[tuple[str, dict]] = []
        with pytest.raises(orchestrator.LegalFinanceCheckpointBlocked):
            cli.run_pipeline(
                "I want a local-first note app for founders.",
                parse_chat_fn=make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE),
                chat_fns=make_worker_chat_fns(),
                review_chat_fn=make_rubric_chat_fn(0.9),
                checkpoint_fn=lambda constraints, lf_result: False,
                on_event=lambda t, d: events.append((t, d)),
            )
        event_types = [t for t, _ in events]
        assert "checkpoint_pending" in event_types
        assert ("checkpoint_result", {"agent": "legal_finance", "approved": False}) in [
            (t, d) for t, d in events if t == "checkpoint_result"
        ]
        assert event_types[-1] == "run_error"

    def test_a_broken_on_event_callback_never_breaks_the_pipeline(self):
        def exploding_callback(event_type, data):
            raise RuntimeError("consumer blew up")

        result = cli.run_pipeline(
            "I want a local-first note app for founders.",
            parse_chat_fn=make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE),
            chat_fns=make_worker_chat_fns(),
            review_chat_fn=make_rubric_chat_fn(0.9),
            on_event=exploding_callback,
        )
        assert set(result.outputs.keys()) == set(orchestrator.WORKER_AGENT_NAMES)


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
