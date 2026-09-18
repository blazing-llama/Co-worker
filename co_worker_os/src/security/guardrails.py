"""Local runtime guardrails: loop circuit breaker, duplicate-call detector, and a
destructive-command interceptor.

FailproofAI (`failproofai policies --install --cli claude`) is the primary path for
hook-level interception (sanitize-api-keys, block-rm-rf, block-force-push,
block-push-master). This module provides the local, dependency-free equivalent so
Sprint 1's exit criteria (a destructive command is blocked) holds even if the
FailproofAI CLI is unavailable in a given environment — see CLAUDE.md's "Unverified
External Packages" section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

try:
    import failproofai  # noqa: F401

    FAILPROOFAI_AVAILABLE = True
except ImportError:
    FAILPROOFAI_AVAILABLE = False


class LoopLimitExceeded(RuntimeError):
    """Raised when an agent task exceeds MAX_AGENT_LOOP_ITERATIONS."""


class DuplicateToolCallDetected(RuntimeError):
    """Raised when the same (tool, args) pair is called twice in one task loop."""


class DestructiveCommandBlocked(RuntimeError):
    """Raised when a command matches a blocked destructive pattern."""


@dataclass
class CircuitBreaker:
    """Bounds a single agent task's tool-call loop to at most `max_iterations`
    calls, and rejects an exact repeat of a prior (tool_name, args) call within
    the same task — the two failure modes that cause silent runaway agent loops.
    """

    max_iterations: int = 5
    _iteration_count: int = field(default=0, init=False)
    _seen_calls: set[tuple[str, str]] = field(default_factory=set, init=False)

    def record_call(self, tool_name: str, args_repr: str) -> None:
        self._iteration_count += 1
        if self._iteration_count > self.max_iterations:
            raise LoopLimitExceeded(
                f"Agent task exceeded {self.max_iterations} tool-call iterations."
            )

        call_key = (tool_name, args_repr)
        if call_key in self._seen_calls:
            raise DuplicateToolCallDetected(
                f"Duplicate tool call detected: {tool_name}({args_repr})"
            )
        self._seen_calls.add(call_key)

    def reset(self) -> None:
        self._iteration_count = 0
        self._seen_calls.clear()

    @property
    def iteration_count(self) -> int:
        return self._iteration_count


# --- Destructive command interception (local fallback for FailproofAI's
# block-rm-rf / block-force-push / block-push-master policies) ---

_BLOCKED_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("block-rm-rf", re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*)\b")),
    ("block-force-push", re.compile(r"\bgit\s+push\b.*(--force\b|-f\b)")),
    ("block-push-master", re.compile(r"\bgit\s+push\b(?!.*--force)(?!.*-f\b).*\b(origin\s+)?(main|master)\b")),
]

# Secret-like patterns to scrub before agent context ingestion (sanitize-api-keys
# fallback). Intentionally conservative — false positives (over-redaction) are
# safer than a leaked key.
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI-style keys
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),  # GitHub tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9\-_/+=]{12,}"),
]


def check_command_allowed(command: str) -> None:
    """Raise DestructiveCommandBlocked if `command` matches a blocked pattern.

    A `git push --force` to a non-main/master branch is allowed to pass the
    push-master check but still blocked by the force-push check — both patterns
    are evaluated independently.
    """
    for policy_name, pattern in _BLOCKED_PATTERNS:
        if pattern.search(command):
            raise DestructiveCommandBlocked(
                f"Command blocked by policy '{policy_name}': {command!r}"
            )


def sanitize_secrets(text: str) -> str:
    """Replace anything matching a known secret pattern with a redaction marker
    before it enters agent context."""
    sanitized = text
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized
