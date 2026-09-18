# Implementation Plan — Co-Worker OS

5 sequential, self-contained sprints. Each sprint is scoped to fit in one focused
session; do not carry unfinished Sprint N work into Sprint N+1 — close it out or
explicitly note it as deferred in this doc first.

## Sprint Status

| Sprint | Scope | Status |
|---|---|---|
| 0 | Scaffolding, docs, CLAUDE.md, pyproject.toml | ✅ Done |
| 1 | Security hooks + Pydantic schemas | ✅ Done |
| 2 | Web/social/video scrapers + local search | ✅ Done |
| 3 | Orchestrator hub + 5 parallel worker agents | ⬜ Not started |
| 4 | 2-layer review gate + Strands Evals diagnostics | ⬜ Not started |
| 5 | Context compaction harness + CLI entry point | ⬜ Not started |

---

## Sprint 1: Security, FailproofAI hooks, Pydantic schemas

**Goal:** No agent can leak a secret, run a destructive command, or exchange
unstructured text with another agent.

- `pip install failproofai` (try; fall back to local hooks in `.failproofai/policies/`
  if install/CLI differs from spec).
- `failproofai policies --install --cli claude`; enable `sanitize-api-keys`,
  `block-rm-rf`, `block-force-push`, `block-push-master`.
- `src/security/guardrails.py`: circuit breaker (max 5 loop iterations), duplicate
  tool-call detector.
- `src/core/schemas.py`: all 6 Pydantic models (`ProductConstraints`,
  `SharkTankVerdict`, `PRDSpec`, `TechStackSpec`, `GTMSentiment`, `LegalFlags`,
  `ReviewReport`).
- `src/core/config.py`: Ollama endpoint config, model routing table, env loading.
- Tests: `tests/test_guardrails.py`, `tests/test_schemas.py` (TDD RED-GREEN).

**Exit criteria:** `pytest tests/test_guardrails.py tests/test_schemas.py` green;
a manual `rm -rf /` attempt in the repo is blocked.

**Result:** 34/34 tests pass. `failproofai` is not available on PyPI in this
environment (confirmed via `pip install failproofai` failure); the local fallback
in `src/security/guardrails.py` (`check_command_allowed`) was verified to block
`rm -rf`, `git push --force`, and `git push origin main`, while allowing a normal
feature-branch push — meeting the exit criteria without the external package.
`.failproofai/policies/co_worker.yaml` documents the intended policy config for
environments where the CLI is available.

## Sprint 2: Web, social, video scrapers + local search

**Goal:** Grounded, token-efficient markdown research with zero paid APIs.

- `src/scrapers/web_scraper.py`: Crawl4AI-based HTML → markdown extractor (primary),
  BeautifulSoup fallback if Crawl4AI unavailable. DuckDuckGo search for query → URLs.
- `src/scrapers/video_scraper.py`: yt-dlp transcript/subtitle extraction
  (`skip_download=True`, `writesubtitles=True`), no video binaries downloaded.
- `src/scrapers/social_scraper.py`: Reddit RSS + forum thread pulls via `feedparser`.
- Tests: fixture-based (recorded HTML/RSS samples, no live network calls in CI).

**Exit criteria:** each scraper returns clean markdown/text from a fixture input
with no external API key required.

**Result:** 10/10 new scraper tests pass (44/44 total). `crawl4ai`, `yt-dlp`,
`beautifulsoup4`, `feedparser`, and `requests` all installed cleanly in this
environment (confirmed via `pip install`), so `web_scraper.py` uses Crawl4AI as
the primary path with the BeautifulSoup+requests fallback verified independently
(`scrape_url(..., crawl4ai_available=False)`). `video_scraper.py` confirmed to
pass `skip_download=True` to yt-dlp and to strip all WEBVTT cue/timestamp markup
before returning transcript markdown. `social_scraper.py` confirmed against a
Reddit Atom feed fixture with HTML-escaped entry content, verified stripped to
plain text. All three modules take an injectable HTTP/downloader dependency, so
the test suite runs fully offline — no live network call was made against a real
Reddit/YouTube/web endpoint in this session.

## Sprint 3: Orchestrator hub + 5 parallel worker agents

**Goal:** Natural-language idea → `ProductConstraints` → 5 concurrent, schema-bound
agent outputs.

- **Before starting:** run `ollama list` / `curl http://localhost:11434/api/tags` to
  confirm `qwen2.5:32b`, `qwen2.5-coder:14b`, `llama3.2:3b` (or equivalents) are
  available. If not, stop and report — do not silently substitute a cloud model.
- `src/agents/orchestrator.py`: parses NL input → `ProductConstraints` (routed to a
  small local model), dispatches to workers via LangGraph parallel edges.
- `src/agents/cofounder.py`, `product_manager.py`, `engineer.py`, `gtm_ops.py`,
  `legal_finance.py`: each consumes `ProductConstraints` only (never re-parses the
  raw prompt) and emits its typed schema.
- Human-in-the-loop checkpoint (`interrupt_before`) ahead of Legal/Finance output.
- Tests: mock Ollama responses; assert schema conformance per agent.

**Exit criteria:** one orchestrator run produces 5 valid, schema-conformant JSON
outputs from a single NL prompt, with Legal/Finance gated behind a checkpoint.

## Sprint 4: 2-layer review gate + Strands Evals diagnostics

**Goal:** No ungrounded or malformed output reaches the user.

- `src/review/evaluator.py`: Layer 1 (Pydantic validation, numeric/budget sanity
  checks, pytest hooks); Layer 2 (LLM rubric scoring against scraped-data grounding
  and constraint adherence). AG2 group-chat pattern for multi-agent cross-review.
- `src/review/repair_loop.py`: bounded (max 3) repair cycle feeding `RepairHints`
  back to the originating agent.
- `src/evals/strands_harness.py`: wraps session logs into `strands-evals` `Session`
  traces; `detect_failures`, `analyze_root_cause`. Local stub fallback if the
  package differs from spec.

**Exit criteria:** an intentionally malformed agent output is caught, repaired
within 3 cycles or explicitly surfaced as failed — never silently passed through.

## Sprint 5: Context compaction harness + CLI entry point

**Goal:** Long sessions don't blow the context window or lose instruction fidelity.

- `src/core/context_manager.py`: progressive summarization of old tool outputs past
  a token threshold; event-driven system-reminder injection before each sub-agent
  dispatch.
- CLI entry point (`co-worker` console script) wiring: NL input → orchestrator →
  review gate → formatted 5-part output.
- Tests: context manager correctly compacts a synthetic long session below threshold.

**Exit criteria:** `co-worker "idea text"` runs end-to-end locally, output is all
5 deliverables, review-gated, with zero cloud calls.
