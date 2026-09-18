"""Shared helper for worker agents. Not a public API surface."""

from __future__ import annotations


def append_feedback(user_prompt: str, feedback: str | None) -> str:
    """Append a repair-loop RepairHints.suggested_fix to a worker's prompt.

    Used only by the bounded repair loop (src/review/repair_loop.py) to hand
    the responsible agent concrete feedback on why its prior output failed
    review, per docs/ImplementationPlan.md Sprint 4.
    """
    if not feedback:
        return user_prompt
    return f"{user_prompt}\n\n--- PRIOR ATTEMPT FAILED REVIEW, FIX THIS ---\n{feedback}"
