# CLAUDE.md — Co-Worker OS Project Invariants

This file is loaded at the start of every terminal session in this repo. It defines
non-negotiable rules that persist across context resets and sprints.

## Identity

You are working inside `co_worker_os`: a 100% local, zero-subscription, multi-agent
"founding startup team" system (Co-Founder, PM, Eng Lead, GTM/Research, Legal/Finance)
running entirely on local Ollama models. There is no cloud LLM fallback and no paid API
in the critical path.

## Core Invariants (never violate)

1. **Zero cloud dependency for reasoning.** All LLM calls go through
   `http://localhost:11434/v1` (Ollama, OpenAI-compatible). Never introduce a
   hosted-LLM SDK call (OpenAI, Anthropic, etc.) into `src/agents/` or `src/review/`.
2. **Zero paid scraping/search.** Web/social/video research uses Crawl4AI, yt-dlp,
   BeautifulSoup, and DuckDuckGo/SearXNG only. Never wire in a paid API key
   (Firecrawl cloud, SerpAPI, etc.) as a required path — cloud fallbacks, if ever
   added, must be optional and off by default.
3. **Schema-first inter-agent communication.** Agents never pass raw free-text to
   each other. Every hop is a validated Pydantic model from `src/core/schemas.py`.
4. **No hallucinated grounding.** Agent outputs (market claims, legal flags, tech
   specs) must cite scraped markdown, local repo files, or schema fields — never
   invented statistics, URLs, or facts.
5. **Bounded execution.** Every agent loop is capped at 5 iterations
   (`src/security/guardrails.py`); every repair loop is capped at 3 iterations
   (`src/review/repair_loop.py`). No unbounded while-loops around an LLM call.
6. **Destructive commands are intercepted, not trusted.** `rm -rf`, force-push, and
   direct pushes to `main`/`master` must be blocked by local hooks before they run.
7. **TDD RED-GREEN.** Every `FR-XXX` requirement gets a `TEST-XXX` written first and
   failing, before the implementation (`IMPL-XXX`) is written.
8. **Document-Driven Development.** `docs/PRD.md`, `docs/Architecture.md`, and
   `docs/ImplementationPlan.md` are the source of truth. If code and docs disagree,
   stop and reconcile the docs first — do not silently drift.

## Sprint Discipline

Work is organized into 5 sequential, self-contained sprints (see
`docs/ImplementationPlan.md`). Do not start Sprint N+1 work inside a Sprint N
session. Use `docs/STARTING_PROMPTS.md` to launch each sprint fresh — this prevents
context bloat and instruction fade-out across long sessions.

## Unverified External Packages

`FailproofAI`, `mvp-builder`, `strands-agents-evals`, and `awesome-free-models` are
external projects this system depends on for tooling (not reasoning). If any fails to
install or its API differs from what a sprint doc assumes, implement the equivalent
behavior locally (see `src/security/guardrails.py`, `src/evals/strands_harness.py`)
rather than blocking the sprint or silently dropping the requirement — and say so in
the sprint report.

## Model Routing

- Heavy reasoning (Shark Tank analysis, PRD generation, TDD code generation):
  `qwen2.5:32b` or `qwen2.5-coder:14b`.
- Lightweight JSON parsing/routing (Orchestrator's `ProductConstraints` extraction):
  `llama3.2:3b` or equivalent small model.
- Before Sprint 3 (agent pipeline), verify local models are pulled:
  `ollama list` or `curl http://localhost:11434/api/tags`.

## Commit Discipline

- Never commit directly to `main`. Work on feature branches.
- Never force-push. Never `git push --force` to any shared branch.
- Never `rm -rf` inside the repo without explicit user confirmation.
