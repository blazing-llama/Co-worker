"""Sprint 7: semantic memory cache for agent LLM calls.

Wraps a ChatFn so that a (system_prompt, user_prompt) pair whose user_prompt
is semantically close (cosine similarity >= threshold, default 0.85) to a
previously seen prompt for the *same system prompt* returns the cached
response instead of making another local model call. Embeddings come from
the locally pulled `nomic-embed-text` model via the local Ollama endpoint --
no cloud embeddings API, matching CLAUDE.md's zero-cloud-dependency rule.

The cache is keyed per system_prompt so agents with different roles never
share cache entries with each other, even if their user prompts happen to be
textually similar.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Callable

import requests

from src.core.config import CACHE_SIMILARITY_THRESHOLD, EMBED_MODEL, OLLAMA_BASE_URL
from src.core.ollama_client import ChatFn, ModelUnavailableError

EmbedFn = Callable[[str], list[float]]


def default_embed_fn(model: str = EMBED_MODEL, base_url: str | None = None) -> EmbedFn:
    """Build a real embedding function against the local Ollama endpoint's
    native /api/embeddings route (not the OpenAI-compatible /v1 path, which
    doesn't expose embeddings for all Ollama versions)."""
    embeddings_url = (base_url or OLLAMA_BASE_URL).replace("/v1", "") + "/api/embeddings"

    def _embed(text: str) -> list[float]:
        try:
            response = requests.post(embeddings_url, json={"model": model, "prompt": text}, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except (requests.exceptions.RequestException, OSError) as exc:
            raise ModelUnavailableError(
                f"Could not reach local Ollama endpoint {embeddings_url!r} for embedding model {model!r}: {exc}"
            ) from exc
        embedding = payload.get("embedding")
        if not embedding:
            raise ModelUnavailableError(f"Ollama returned no embedding for model {model!r}: {payload}")
        return embedding

    return _embed


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Embedding dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class _CacheEntry:
    prompt: str
    embedding: list[float]
    response: str


@dataclass
class SemanticCache:
    """In-process semantic cache, keyed per system_prompt. Not persisted to
    disk -- scoped to a single pipeline run/process, same lifetime as the
    ThreadPoolExecutor dispatch it wraps.

    Thread-safe: dispatch() (src/agents/orchestrator.py) runs up to
    MAX_CONCURRENT_AGENTS worker chat_fns concurrently, and a single cache
    instance shared across a run must tolerate concurrent get()/put() calls.
    """

    embed_fn: EmbedFn
    threshold: float = CACHE_SIMILARITY_THRESHOLD
    _entries: dict[str, list[_CacheEntry]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    hits: int = 0
    misses: int = 0

    def get(self, system_prompt: str, user_prompt: str) -> str | None:
        with self._lock:
            entries = list(self._entries.get(system_prompt, []))

        if not entries:
            with self._lock:
                self.misses += 1
            return None

        query_embedding = self.embed_fn(user_prompt)
        best_score = -1.0
        best_entry: _CacheEntry | None = None
        for entry in entries:
            score = cosine_similarity(query_embedding, entry.embedding)
            if score > best_score:
                best_score = score
                best_entry = entry

        with self._lock:
            if best_entry is not None and best_score >= self.threshold:
                self.hits += 1
                return best_entry.response
            self.misses += 1
            return None

    def put(self, system_prompt: str, user_prompt: str, response: str) -> None:
        embedding = self.embed_fn(user_prompt)
        with self._lock:
            self._entries.setdefault(system_prompt, []).append(
                _CacheEntry(prompt=user_prompt, embedding=embedding, response=response)
            )


def wrap_chat_fn(chat_fn: ChatFn, cache: SemanticCache) -> ChatFn:
    """Wrap `chat_fn` so identical/semantically-similar (system_prompt,
    user_prompt) pairs reuse a cached response instead of calling the model
    again. Cache misses fall through to `chat_fn` and populate the cache."""

    def _cached_chat(system_prompt: str, user_prompt: str) -> str:
        cached = cache.get(system_prompt, user_prompt)
        if cached is not None:
            return cached
        response = chat_fn(system_prompt, user_prompt)
        cache.put(system_prompt, user_prompt, response)
        return response

    return _cached_chat
