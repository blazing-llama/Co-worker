"""TDD tests for src/core/context_manager.py: progressive compaction of old
tool/agent outputs past a token threshold, and event-driven system-reminder
injection ahead of sub-agent dispatch.
"""

from __future__ import annotations

from src.core.context_manager import ContextManager, estimate_tokens


class TestEstimateTokens:
    def test_empty_string_is_zero_tokens(self):
        assert estimate_tokens("") == 0

    def test_longer_text_estimates_more_tokens(self):
        assert estimate_tokens("a" * 400) > estimate_tokens("a" * 40)


class TestContextManagerAdd:
    def test_add_entry_below_threshold_keeps_full_content(self):
        cm = ContextManager(token_threshold=10_000)
        cm.add_entry("cofounder", "short output")
        assert cm.entries[0].content == "short output"
        assert cm.entries[0].summarized is False

    def test_entries_accumulate_in_order(self):
        cm = ContextManager(token_threshold=10_000)
        cm.add_entry("a", "first")
        cm.add_entry("b", "second")
        assert [e.label for e in cm.entries] == ["a", "b"]


class TestContextManagerCompaction:
    def test_compacts_oldest_entries_when_threshold_exceeded(self):
        def fake_summarize(label: str, content: str) -> str:
            return f"[summary of {label}, {len(content)} chars]"

        cm = ContextManager(token_threshold=50, summarize_fn=fake_summarize)
        cm.add_entry("agent_1", "x" * 100)  # ~25 tokens, under threshold alone
        cm.add_entry("agent_2", "y" * 100)  # pushes total over threshold

        # The oldest entry should now be compacted; the newest stays full.
        assert cm.entries[0].summarized is True
        assert cm.entries[0].content.startswith("[summary of agent_1")
        assert cm.entries[-1].summarized is False
        assert cm.entries[-1].content == "y" * 100

    def test_never_compacts_the_most_recent_entry(self):
        def fake_summarize(label: str, content: str) -> str:
            return "[summary]"

        cm = ContextManager(token_threshold=10, summarize_fn=fake_summarize)
        cm.add_entry("only_entry", "z" * 200)
        # Even though this single entry exceeds the threshold, it's the most
        # recent (and only) entry -- compacting it would destroy the very
        # context the next agent call needs, so it must stay uncompacted.
        assert cm.entries[0].summarized is False

    def test_total_tokens_drops_after_compaction(self):
        def fake_summarize(label: str, content: str) -> str:
            return "short"

        cm = ContextManager(token_threshold=50, summarize_fn=fake_summarize)
        cm.add_entry("agent_1", "x" * 200)
        before = cm.total_tokens()
        cm.add_entry("agent_2", "y" * 200)
        after = cm.total_tokens()
        # Compaction of agent_1 should keep total from growing linearly.
        assert after < before + estimate_tokens("y" * 200)

    def test_default_summarize_fn_truncates_without_llm_call(self):
        cm = ContextManager(token_threshold=20)
        cm.add_entry("agent_1", "word " * 200)
        cm.add_entry("agent_2", "trigger compaction " * 50)
        assert cm.entries[0].summarized is True
        assert len(cm.entries[0].content) < len("word " * 200)


class TestSystemReminder:
    def test_build_dispatch_reminder_mentions_schema_first_invariant(self):
        cm = ContextManager(token_threshold=10_000)
        reminder = cm.build_dispatch_reminder(agent_name="cofounder")
        assert "cofounder" in reminder
        assert "ProductConstraints" in reminder

    def test_reminder_is_recorded_as_an_entry(self):
        cm = ContextManager(token_threshold=10_000)
        cm.build_dispatch_reminder(agent_name="engineer")
        assert any(e.label == "system_reminder:engineer" for e in cm.entries)
