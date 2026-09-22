"""TDD tests for src/agents/. All LLM calls are stubbed via a fake ChatFn so
the suite runs fully offline — no real Ollama endpoint is required to pass.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.agents import cofounder, engineer, gtm_ops, legal_finance, orchestrator, product_manager
from src.core.ollama_client import MalformedAgentOutput
from src.core.schemas import ProductConstraints, Region

# --- Fixtures -------------------------------------------------------------

CONSTRAINTS = ProductConstraints(
    idea_summary="A local-first note-taking app for founders.",
    target_persona="Solo indie founder",
    budget_usd=5000,
    timeline_weeks=8,
    tech_constraints=["must run offline"],
    region=Region.INDIA,
)

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
        "defensibility_notes": "Weak moat, fast follower risk",
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
        "customer_feedback_themes": [
            {
                "theme": "Users want offline mode",
                "supporting_quote_or_stat": "I lose data every time wifi drops",
                "source_url": "https://reddit.com/r/productivity/example",
                "confidence": "medium",
            }
        ],
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


def make_fake_chat_fn(raw_response: str, call_log: list | None = None):
    def _fake(system_prompt: str, user_prompt: str) -> str:
        if call_log is not None:
            call_log.append((system_prompt, user_prompt))
        return raw_response

    return _fake


# --- Orchestrator: NL parsing ---------------------------------------------


class TestOrchestratorParseConstraints:
    def test_parses_raw_prompt_into_product_constraints(self):
        chat_fn = make_fake_chat_fn(RAW_ORCHESTRATOR_PARSE)
        constraints = orchestrator.parse_constraints(
            "I want a local-first note app for founders.", chat_fn=chat_fn
        )
        assert isinstance(constraints, ProductConstraints)
        assert constraints.region == Region.INDIA

    def test_raises_malformed_output_on_invalid_json(self):
        chat_fn = make_fake_chat_fn("not json at all")
        with pytest.raises(MalformedAgentOutput):
            orchestrator.parse_constraints("some idea", chat_fn=chat_fn)

    def test_raises_malformed_output_on_schema_violation(self):
        bad_json = json.dumps({"idea_summary": "x"})  # missing required fields
        chat_fn = make_fake_chat_fn(bad_json)
        with pytest.raises(MalformedAgentOutput):
            orchestrator.parse_constraints("some idea", chat_fn=chat_fn)


# --- Orchestrator: concurrent dispatch -------------------------------------


class TestOrchestratorDispatch:
    def test_dispatches_to_all_five_agents_with_constraints_only(self):
        call_logs: dict[str, list] = {name: [] for name in orchestrator.WORKER_AGENT_NAMES}
        chat_fns = {
            "cofounder": make_fake_chat_fn(RAW_COFOUNDER, call_logs["cofounder"]),
            "product_manager": make_fake_chat_fn(RAW_PM, call_logs["product_manager"]),
            "engineer": make_fake_chat_fn(RAW_ENGINEER, call_logs["engineer"]),
            "gtm_ops": make_fake_chat_fn(RAW_GTM, call_logs["gtm_ops"]),
            "legal_finance": make_fake_chat_fn(RAW_LEGAL, call_logs["legal_finance"]),
        }

        results = orchestrator.dispatch(CONSTRAINTS, chat_fns=chat_fns)

        assert set(results.keys()) == set(orchestrator.WORKER_AGENT_NAMES)
        assert isinstance(results["cofounder"], cofounder.SharkTankVerdict)
        assert isinstance(results["product_manager"], product_manager.PRDSpec)
        assert isinstance(results["engineer"], engineer.TechStackSpec)
        assert isinstance(results["gtm_ops"], gtm_ops.GTMSentiment)
        assert isinstance(results["legal_finance"], legal_finance.LegalFlags)

        # Every worker must be called exactly once, with the constraints
        # serialized into the prompt -- never the raw user string.
        for name, log in call_logs.items():
            assert len(log) == 1
            _system_prompt, user_prompt = log[0]
            assert "local-first note-taking app" in user_prompt  # from constraints.idea_summary
            assert user_prompt != "I want a local-first note app for founders."  # never the raw NL prompt

    def test_dispatch_runs_workers_with_bounded_concurrency(self):
        # Sprint 7: dispatch no longer fires all 5 workers at once (that
        # thrashes VRAM on a single shared local model) -- it caps concurrent
        # in-flight calls at config.MAX_CONCURRENT_AGENTS. This asserts both
        # halves of that: at least 2 calls do overlap (not fully sequential),
        # and at no point do more than MAX_CONCURRENT_AGENTS run together.
        import threading
        import time

        from src.core.config import MAX_CONCURRENT_AGENTS

        lock = threading.Lock()
        state = {"current": 0, "max_seen": 0, "overlapped": False}

        def make_blocking_chat_fn(raw_response: str):
            def _fake(system_prompt: str, user_prompt: str) -> str:
                with lock:
                    state["current"] += 1
                    state["max_seen"] = max(state["max_seen"], state["current"])
                    if state["current"] > 1:
                        state["overlapped"] = True
                time.sleep(0.2)
                with lock:
                    state["current"] -= 1
                return raw_response

            return _fake

        chat_fns = {
            "cofounder": make_blocking_chat_fn(RAW_COFOUNDER),
            "product_manager": make_blocking_chat_fn(RAW_PM),
            "engineer": make_blocking_chat_fn(RAW_ENGINEER),
            "gtm_ops": make_blocking_chat_fn(RAW_GTM),
            "legal_finance": make_blocking_chat_fn(RAW_LEGAL),
        }

        start = time.monotonic()
        results = orchestrator.dispatch(CONSTRAINTS, chat_fns=chat_fns)
        elapsed = time.monotonic() - start

        assert len(results) == 5
        assert state["overlapped"] is True  # not fully sequential
        assert state["max_seen"] <= MAX_CONCURRENT_AGENTS  # never exceeds the bound
        assert elapsed < 1.5  # 5 calls at concurrency 2, 0.2s each, would hang/timeout if serialized far beyond this


class TestLegalFinanceCheckpoint:
    def _chat_fns(self):
        return {
            "cofounder": make_fake_chat_fn(RAW_COFOUNDER),
            "product_manager": make_fake_chat_fn(RAW_PM),
            "engineer": make_fake_chat_fn(RAW_ENGINEER),
            "gtm_ops": make_fake_chat_fn(RAW_GTM),
            "legal_finance": make_fake_chat_fn(RAW_LEGAL),
        }

    def test_checkpoint_approval_releases_legal_finance_result(self):
        results = orchestrator.dispatch(
            CONSTRAINTS, chat_fns=self._chat_fns(), checkpoint_fn=lambda constraints, lf_result: True
        )
        assert "legal_finance" in results

    def test_checkpoint_denial_blocks_release(self):
        with pytest.raises(orchestrator.LegalFinanceCheckpointBlocked):
            orchestrator.dispatch(
                CONSTRAINTS, chat_fns=self._chat_fns(), checkpoint_fn=lambda constraints, lf_result: False
            )

    def test_checkpoint_receives_constraints_and_legal_finance_result(self):
        received = {}

        def checkpoint(constraints, lf_result):
            received["constraints"] = constraints
            received["lf_result"] = lf_result
            return True

        orchestrator.dispatch(CONSTRAINTS, chat_fns=self._chat_fns(), checkpoint_fn=checkpoint)
        assert received["constraints"] is CONSTRAINTS
        assert received["lf_result"].ca_cs_lawyer_required is True

    def test_no_checkpoint_fn_releases_unconditionally(self):
        results = orchestrator.dispatch(CONSTRAINTS, chat_fns=self._chat_fns())
        assert "legal_finance" in results


# --- Individual worker agents ----------------------------------------------


class TestCofounderAgent:
    def test_run_returns_valid_shark_tank_verdict(self):
        chat_fn = make_fake_chat_fn(RAW_COFOUNDER)
        verdict = cofounder.run(CONSTRAINTS, chat_fn=chat_fn)
        assert verdict.tam_usd == 1_000_000
        assert len(verdict.risks) == 4

    def test_prompt_includes_constraints_not_raw_string(self):
        log = []
        chat_fn = make_fake_chat_fn(RAW_COFOUNDER, log)
        cofounder.run(CONSTRAINTS, chat_fn=chat_fn)
        _, user_prompt = log[0]
        assert CONSTRAINTS.target_persona in user_prompt


class TestProductManagerAgent:
    def test_run_returns_valid_prd_spec(self):
        chat_fn = make_fake_chat_fn(RAW_PM)
        spec = product_manager.run(CONSTRAINTS, chat_fn=chat_fn)
        assert spec.requirements[0].id == "FR-001"


class TestEngineerAgent:
    def test_run_returns_valid_tech_stack_spec(self):
        chat_fn = make_fake_chat_fn(RAW_ENGINEER)
        spec = engineer.run(CONSTRAINTS, chat_fn=chat_fn)
        assert spec.test_specs[0].id == "TEST-001"


class TestGtmOpsAgent:
    def test_run_returns_valid_gtm_sentiment(self):
        chat_fn = make_fake_chat_fn(RAW_GTM)
        sentiment = gtm_ops.run(CONSTRAINTS, chat_fn=chat_fn)
        assert sentiment.customer_feedback_themes[0].source_url.startswith("https://")

    def test_run_accepts_optional_scraped_context(self):
        log = []
        chat_fn = make_fake_chat_fn(RAW_GTM, log)
        gtm_ops.run(CONSTRAINTS, chat_fn=chat_fn, scraped_context="## Reddit thread\n\nUsers want offline mode.")
        _, user_prompt = log[0]
        assert "Reddit thread" in user_prompt


class TestLegalFinanceAgent:
    def test_run_returns_valid_legal_flags(self):
        chat_fn = make_fake_chat_fn(RAW_LEGAL)
        flags = legal_finance.run(CONSTRAINTS, chat_fn=chat_fn)
        assert flags.ca_cs_lawyer_required is True

    def test_prompt_references_india_dpdp_and_gst_when_region_is_india(self):
        log = []
        chat_fn = make_fake_chat_fn(RAW_LEGAL, log)
        legal_finance.run(CONSTRAINTS, chat_fn=chat_fn)
        system_prompt, _ = log[0]
        assert "DPDP" in system_prompt
        assert "GST" in system_prompt


# --- Model routing verification (config.py) --------------------------------


class TestModelRoutingVerification:
    def test_verify_model_routing_reports_missing_models(self):
        from src.core.config import verify_model_routing

        result = verify_model_routing(available_models=["llama3.2:3b"])
        assert result["llama3.2:3b"] is True
        assert result["qwen2.5:32b"] is False

    def test_list_local_models_returns_empty_on_unreachable_ollama(self):
        from src.core.config import list_local_models

        def failing_get(url, timeout=5):
            raise ConnectionError("no ollama here")

        assert list_local_models(http_get=failing_get) == []


class TestQuickModeRouting:
    """model_for() is the only place agents (and orchestrator.dispatch, via
    each agent's default_chat_fn(model_for(...))) get their model name from.
    QUICK_MODE is env-driven and read at import time, so these tests exercise
    the underlying logic directly rather than reimporting the module."""

    def test_orchestrator_parse_always_uses_fast_model_regardless_of_quick_mode(self):
        from src.core import config

        assert config.model_for("orchestrator_parse") == config.FAST_MODEL

    def test_quick_mode_routes_reasoning_agents_to_quick_heavy_model_not_fast_model(self):
        from src.core import config

        if config.QUICK_MODE:
            for task in ("cofounder", "product_manager", "engineer", "gtm_ops", "legal_finance", "review_rubric"):
                assert config.model_for(task) == config.QUICK_HEAVY_MODEL
                assert config.model_for(task) != config.FAST_MODEL
