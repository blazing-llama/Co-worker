"""Context compaction + event-driven system reminders.

Per CLAUDE.md's "no context window bloat or instruction fade-out" invariant:
older tool/agent outputs get progressively summarized once the running session
crosses a token threshold, and a short system reminder is injected before each
sub-agent dispatch to counteract instruction fade-out on long runs (the
lazy-tool-discovery / adaptive-context-compaction / event-driven-reminders
pattern from docs/PRD.md's tooling manifest).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

SummarizeFn = Callable[[str, str], str]
"""(label, content) -> summarized content."""

_CHARS_PER_TOKEN = 4  # rough, model-agnostic heuristic; good enough for a local threshold trigger


def estimate_tokens(text: str) -> int:
    """Cheap token estimate (chars / 4) -- no tokenizer dependency needed just
    to decide whether to compact."""
    return len(text) // _CHARS_PER_TOKEN


def _default_summarize(label: str, content: str, max_chars: int = 200) -> str:
    """Truncation-based fallback summarizer: no LLM call required. Real
    summarization can be swapped in via `summarize_fn` (e.g. a chat_fn-backed
    summarizer) without changing ContextManager's compaction logic."""
    if len(content) <= max_chars:
        return content
    return f"[compacted: {label}, {len(content)} chars] {content[:max_chars]}..."


@dataclass
class ContextEntry:
    label: str
    content: str
    summarized: bool = False


@dataclass
class ContextManager:
    """Tracks one orchestrator run's tool/agent outputs and compacts the
    oldest ones once `token_threshold` is exceeded. The most recent entry is
    never compacted -- it's what the next agent call actually needs."""

    token_threshold: int = 4000
    summarize_fn: SummarizeFn = field(default=_default_summarize)
    entries: list[ContextEntry] = field(default_factory=list)

    def add_entry(self, label: str, content: str) -> ContextEntry:
        entry = ContextEntry(label=label, content=content)
        self.entries.append(entry)
        self._compact_if_needed()
        return entry

    def total_tokens(self) -> int:
        return sum(estimate_tokens(e.content) for e in self.entries)

    def _compact_if_needed(self) -> None:
        # Compact oldest-first, but never the last (most recent) entry.
        idx = 0
        while self.total_tokens() >= self.token_threshold and idx < len(self.entries) - 1:
            entry = self.entries[idx]
            if not entry.summarized:
                entry.content = self.summarize_fn(entry.label, entry.content)
                entry.summarized = True
            idx += 1

    def build_dispatch_reminder(self, agent_name: str) -> str:
        """Event-driven reminder injected immediately before dispatching to
        `agent_name`, restating the schema-first invariant so it survives a
        long context window rather than fading out of the model's attention."""
        reminder = (
            f"[system reminder before dispatching to '{agent_name}'] "
            f"Consume ONLY the given ProductConstraints JSON -- never re-read or "
            f"re-interpret the user's raw prompt. Return ONLY JSON matching your "
            f"schema, grounded in the given constraints/context, no invented facts."
        )
        self.add_entry(f"system_reminder:{agent_name}", reminder)
        return reminder
