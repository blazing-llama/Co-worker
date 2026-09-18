# Starting Prompts — Copy/Paste per Sprint

Use exactly one of these per fresh terminal session, in order. Each prompt assumes
`CLAUDE.md` and `docs/ImplementationPlan.md` are already in the repo (they are, as
of Phase 0). Do not paste more than one sprint's prompt into a single session.

---

## Sprint 1 Prompt

```
Read CLAUDE.md and docs/ImplementationPlan.md (Sprint 1 section only). Implement
Sprint 1: install/configure FailproofAI hooks in .failproofai/policies/ (or an
equivalent local fallback if the package/CLI differs from spec), write
src/security/guardrails.py with a 5-iteration circuit breaker and duplicate
tool-call detector, write src/core/schemas.py with all 6 Pydantic contracts from
docs/PRD.md, and src/core/config.py for Ollama endpoint/model routing config.
Write failing tests first (tests/test_guardrails.py, tests/test_schemas.py), then
implement until green. Update the Sprint 1 row in docs/ImplementationPlan.md to
Done when finished. Report exit criteria results.
```

## Sprint 2 Prompt

```
Read CLAUDE.md and docs/ImplementationPlan.md (Sprint 2 section only). Implement
the local scraping pipeline: src/scrapers/web_scraper.py (Crawl4AI primary,
BeautifulSoup fallback, DuckDuckGo search for URL discovery),
src/scrapers/video_scraper.py (yt-dlp transcript-only extraction, no video
download), src/scrapers/social_scraper.py (Reddit RSS via feedparser). No paid API
keys anywhere in this sprint. Use fixture-based tests (no live network calls
required to pass). Update docs/ImplementationPlan.md when done.
```

## Sprint 3 Prompt

```
Read CLAUDE.md and docs/ImplementationPlan.md (Sprint 3 section only). FIRST run
`ollama list` and/or `curl http://localhost:11434/api/tags` and report what's
available — stop and ask before proceeding if qwen2.5:32b / qwen2.5-coder:14b /
llama3.2:3b (or reasonable equivalents) are missing. Then implement
src/agents/orchestrator.py (NL -> ProductConstraints -> LangGraph parallel
dispatch) and the 5 worker agents (cofounder.py, product_manager.py, engineer.py,
gtm_ops.py, legal_finance.py), each consuming only ProductConstraints and
emitting its typed schema. Add a human-in-the-loop checkpoint before
legal_finance output. Mock Ollama in tests. Update docs/ImplementationPlan.md
when done.
```

## Sprint 4 Prompt

```
Read CLAUDE.md and docs/ImplementationPlan.md (Sprint 4 section only). Implement
src/review/evaluator.py (Layer 1 schema/numeric/pytest checks, Layer 2 LLM rubric
grounding check, AG2 group-chat cross-review), src/review/repair_loop.py (max 3
bounded repair cycles with RepairHints), and src/evals/strands_harness.py
(strands-agents-evals Session wrapping, detect_failures, analyze_root_cause — or
an equivalent local stub if the package differs from spec). Test with an
intentionally malformed agent output and confirm it's caught/repaired/surfaced,
never silently passed. Update docs/ImplementationPlan.md when done.
```

## Sprint 5 Prompt

```
Read CLAUDE.md and docs/ImplementationPlan.md (Sprint 5 section only). Implement
src/core/context_manager.py (progressive summarization past a token threshold,
event-driven system-reminder injection before sub-agent dispatch) and a
`co-worker` CLI entry point wiring NL input through orchestrator -> review gate ->
formatted 5-part output. Test context compaction on a synthetic long session.
Confirm `co-worker "idea text"` runs end-to-end with zero cloud calls. Update
docs/ImplementationPlan.md when done.
```
