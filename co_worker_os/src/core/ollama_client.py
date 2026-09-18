"""Thin local-Ollama chat client + strict JSON-to-Pydantic parsing helper.

Every agent calls the local Ollama OpenAI-compatible endpoint through
`build_chat_fn`, never a cloud LLM SDK. The actual network call is isolated in
one function so tests inject a fake and run fully offline (see
tests/test_agents.py) while production code talks to the real endpoint from
src/core/config.py.
"""

from __future__ import annotations

import json
from typing import Callable, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from src.core.config import OllamaSettings, get_settings

ChatFn = Callable[[str, str], str]
"""A chat function: (system_prompt, user_prompt) -> raw model text response."""

T = TypeVar("T", bound=BaseModel)


class ModelUnavailableError(RuntimeError):
    """Raised when the local Ollama endpoint or a routed model isn't reachable."""


class MalformedAgentOutput(ValueError):
    """Raised when an agent's raw LLM output fails JSON parse or schema validation.

    Never silently coerced or guessed — the caller (review/repair loop, Sprint 4)
    is responsible for deciding what happens next.
    """

    def __init__(self, message: str, raw_output: str):
        super().__init__(message)
        self.raw_output = raw_output


def default_chat_fn(model: str, settings: OllamaSettings | None = None) -> ChatFn:
    """Build a real chat function bound to `model` against the local Ollama
    OpenAI-compatible endpoint. Lazily imports `openai` so this module stays
    importable (and mockable) even if the package isn't installed."""
    settings = settings or get_settings()

    def _chat(system_prompt: str, user_prompt: str) -> str:
        import openai

        client = openai.OpenAI(base_url=settings.base_url, api_key=settings.api_key)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
        except (
            openai.APIConnectionError,
            requests.exceptions.ConnectionError,
            OSError,
        ) as exc:
            raise ModelUnavailableError(
                f"Could not reach local Ollama endpoint {settings.base_url!r} for model {model!r}: {exc}"
            ) from exc
        return response.choices[0].message.content or ""

    return _chat


def parse_json_response(raw_output: str, response_model: type[T]) -> T:
    """Parse and validate `raw_output` (expected to be a JSON object string)
    against `response_model`. Raises MalformedAgentOutput on any failure — the
    raw text is preserved on the exception for the repair loop to inspect."""
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise MalformedAgentOutput(f"Agent output was not valid JSON: {exc}", raw_output) from exc

    try:
        return response_model.model_validate(data)
    except ValidationError as exc:
        raise MalformedAgentOutput(
            f"Agent output failed {response_model.__name__} validation: {exc}", raw_output
        ) from exc
