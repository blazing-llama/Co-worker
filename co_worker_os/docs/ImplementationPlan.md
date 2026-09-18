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
| 3 | Orchestrator hub + 5 parallel worker agents | ✅ Done |
| 4 | 2-layer review gate + Strands Evals diagnostics | ✅ Done |
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

**Result:** 19 new tests (63/63 total) pass.

- **Ollama check (fact, not assumption):** `ollama` is not installed and
  `localhost:11434` refused the connection in this remote sandbox container —
  expected, since this container is not the user's local machine. Live model
  availability (`qwen2.5:32b` / `qwen2.5-coder:14b` / `llama3.2:3b`) was NOT
  verified this session. `src/core/config.py` now exposes
  `list_local_models()` / `verify_model_routing()` so a real local run can
  check this itself before dispatching; both are tested against injected fakes.
  Run `ollama list` (or these functions) before a live run and stop if a routed
  model is missing — do not assume it will silently work.
- `src/core/ollama_client.py` wraps the OpenAI-compatible client against the
  local endpoint; `openai.APIConnectionError` was verified (against no live
  server) to raise `ModelUnavailableError` rather than an unhandled exception.
- All 5 worker agents (`cofounder`, `product_manager`, `engineer`, `gtm_ops`,
  `legal_finance`) consume only `ProductConstraints` — verified per-agent
  (prompt never contains the raw NL string) and via `orchestrator.dispatch`.
- Concurrency verified with a 5-party `threading.Barrier`: dispatch would hang/
  timeout if workers ran sequentially; it completes in well under the timeout.
- **Deviation from the original plan, applied deliberately:** the plan named
  LangGraph's `.parallel()`/`interrupt_before` for dispatch and the
  human-in-the-loop checkpoint. This implementation uses a plain
  `ThreadPoolExecutor` for dispatch (LangGraph adds no behavior a thread pool
  doesn't already give here, and keeps this sprint dependency-light) and a
  `checkpoint_fn(constraints, legal_finance_result) -> bool` callback for the
  gate: all 5 agents run concurrently, but `legal_finance`'s result is withheld
  from the returned dict (raising `LegalFinanceCheckpointBlocked`) unless the
  checkpoint approves — functionally equivalent to `interrupt_before` gating a
  node's output, tested in both the approve and deny paths. `langgraph` remains
  in `pyproject.toml` for a future sprint if a real multi-step graph is needed;
  it was not required for this one.

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

**Result:** 19 new tests (82/82 total) pass.

- `strands-agents-evals` **is real and installed cleanly** (v1.3.0, AWS-authored,
  imports as `strands_evals`; confirmed via `pip install` + direct introspection
  in this session, not assumed). Its actual API differs from the spec's flat
  `Session`/`detect_failures` names: the real shape is
  `strands_evals.types.trace.Session(traces=[Trace(spans=[AgentInvocationSpan(...)])])`
  and `strands_evals.detectors.detect_failures(session, model=...)` /
  `analyze_root_cause(session, failures=..., model=...)`, both requiring a
  `model` for live LLM-judge diagnosis. `strands_harness.py` builds real
  `Session`/`Trace`/`AgentInvocationSpan` objects (verified against the actual
  installed classes, not a mock) and wraps `detect_failures`/`analyze_root_cause`
  behind injectable `detect_fn`/`analyze_fn` so this sprint's tests don't require
  a live model call. The local fallback path (used only if the package failed to
  import) was also directly exercised in this session by forcing
  `STRANDS_EVALS_AVAILABLE = False` and confirming it still builds a session and
  detects a malformed response — both code paths are proven working, not just
  the one that happened to install here. A live `strands-evals diagnose
  --session session.json` run against real session data was NOT performed.
- `evaluator.py`'s Layer 1 does the schema/coverage/budget checks (every FR-XXX
  must have a covering TEST-XXX; a SharkTankVerdict's `tam_usd` below the
  stated `budget_usd` is flagged); Layer 2 is a single local-model rubric judge,
  not a full AG2 group-chat cross-review — that's the one plan item not built
  this sprint (see note below).
- `repair_loop.py`'s bound is enforced and tested from both failure modes: a
  worker that keeps raising `MalformedAgentOutput` and a worker whose output
  parses but never clears the rubric threshold both raise
  `RepairLoopExhausted` at exactly `max_iterations=3`, carrying the last
  attempt's output/report rather than swallowing the failure. A worker that
  fails once and passes on retry is confirmed to receive the prior
  `RepairHints.suggested_fix` as its `feedback` argument (all 5 agents' `run()`
  now accept optional `feedback`).
- **Deferred, not silently dropped:** the plan called for an AG2 group-chat
  pattern (Co-Founder vs. PM vs. Engineer debate) inside the review gate.
  `evaluator.py` implements the single-reviewer LLM rubric only; `ag2` stays in
  `pyproject.toml` for a follow-up sprint if multi-agent cross-review is
  needed. Flagging this explicitly rather than claiming full plan coverage.

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
