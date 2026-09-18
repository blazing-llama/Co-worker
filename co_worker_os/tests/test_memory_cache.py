"""TDD tests for src/core/memory_cache.py (Sprint 7 semantic memory cache).

All embeddings are stubbed via a fake EmbedFn so the suite runs fully
offline -- no real Ollama endpoint required, same convention as
tests/test_agents.py's fake ChatFn.
"""

from __future__ import annotations

import pytest

from src.core.memory_cache import SemanticCache, cosine_similarity, wrap_chat_fn


def make_fake_embed_fn(vectors: dict[str, list[float]]):
    """Returns embeddings by exact prompt-text lookup -- deterministic and
    offline, no real embedding model involved."""

    def _embed(text: str) -> list[float]:
        return vectors[text]

    return _embed


class TestCosineSimilarity:
    def test_identical_vectors_are_similarity_one(self):
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_are_similarity_zero(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors_are_similarity_negative_one(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_zero_vector_is_similarity_zero_not_a_divide_by_zero_error(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_mismatched_dimensions_raises(self):
        with pytest.raises(ValueError):
            cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


class TestSemanticCacheGetPut:
    def test_miss_on_empty_cache(self):
        cache = SemanticCache(embed_fn=make_fake_embed_fn({"a": [1.0, 0.0]}))
        assert cache.get("system", "a") is None
        assert cache.misses == 1
        assert cache.hits == 0

    def test_hit_when_similarity_at_or_above_threshold(self):
        vectors = {"idea A": [1.0, 0.0], "idea A near-dup": [0.99, 0.01]}
        cache = SemanticCache(embed_fn=make_fake_embed_fn(vectors), threshold=0.85)
        cache.put("system", "idea A", "cached response")

        result = cache.get("system", "idea A near-dup")

        assert result == "cached response"
        assert cache.hits == 1

    def test_miss_when_similarity_below_threshold(self):
        vectors = {"idea A": [1.0, 0.0], "totally different idea": [0.0, 1.0]}
        cache = SemanticCache(embed_fn=make_fake_embed_fn(vectors), threshold=0.85)
        cache.put("system", "idea A", "cached response")

        result = cache.get("system", "totally different idea")

        assert result is None
        assert cache.misses == 1

    def test_cache_is_scoped_per_system_prompt(self):
        # Same user_prompt text, different agent roles -- must never share a
        # cache entry even though the embedding would be identical.
        vectors = {"idea A": [1.0, 0.0]}
        cache = SemanticCache(embed_fn=make_fake_embed_fn(vectors), threshold=0.85)
        cache.put("cofounder system prompt", "idea A", "cofounder cached response")

        result = cache.get("product_manager system prompt", "idea A")

        assert result is None


class TestWrapChatFn:
    def test_cache_hit_never_calls_underlying_chat_fn(self):
        calls = []

        def real_chat_fn(system_prompt: str, user_prompt: str) -> str:
            calls.append((system_prompt, user_prompt))
            return "real response"

        vectors = {"idea A": [1.0, 0.0], "idea A near-dup": [0.99, 0.01]}
        cache = SemanticCache(embed_fn=make_fake_embed_fn(vectors), threshold=0.85)
        cached_fn = wrap_chat_fn(real_chat_fn, cache)

        first = cached_fn("system", "idea A")
        second = cached_fn("system", "idea A near-dup")

        assert first == "real response"
        assert second == "real response"  # served from cache, not a second real call
        assert len(calls) == 1

    def test_cache_miss_calls_underlying_chat_fn_and_stores_result(self):
        calls = []

        def real_chat_fn(system_prompt: str, user_prompt: str) -> str:
            calls.append((system_prompt, user_prompt))
            return f"response for {user_prompt}"

        vectors = {"idea A": [1.0, 0.0], "idea B": [0.0, 1.0]}
        cache = SemanticCache(embed_fn=make_fake_embed_fn(vectors), threshold=0.85)
        cached_fn = wrap_chat_fn(real_chat_fn, cache)

        first = cached_fn("system", "idea A")
        second = cached_fn("system", "idea B")

        assert first == "response for idea A"
        assert second == "response for idea B"
        assert len(calls) == 2

    def test_concurrent_get_put_does_not_corrupt_cache(self):
        import threading

        vectors = {f"idea {i}": [float(i), 1.0] for i in range(20)}
        cache = SemanticCache(embed_fn=make_fake_embed_fn(vectors), threshold=0.999)

        def worker(i: int) -> None:
            cache.put("system", f"idea {i}", f"response {i}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(cache._entries["system"]) == 20
        for i in range(20):
            assert cache.get("system", f"idea {i}") == f"response {i}"
