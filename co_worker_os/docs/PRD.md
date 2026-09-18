# PRD: Co-Worker OS — Local Multi-Agent Startup Team

## 1. Problem Statement

Founders and small teams need Shark-Tank-caliber strategic pushback, PM/eng rigor,
market research, and legal/finance risk-flagging — without paying for multiple SaaS
subscriptions or sending proprietary product ideas to third-party cloud LLMs.

## 2. Vision

A single local system where a user describes a product idea in natural language and
receives, in one pass, five grounded, structured deliverables:

1. A Shark Tank-style viability verdict (unit economics, TAM/SAM, risk).
2. A PRD with user flows and an FR-XXX requirements matrix.
3. A technical architecture and TDD test plan.
4. A GTM/market-sentiment report grounded in scraped real-world data.
5. A legal/finance compliance flag list (India DPDP/GST-first, with global flags).

All reasoning runs on local Ollama models. All research is grounded in scraped
markdown, not model memory.

## 3. Users / Personas

- **Solo/early-stage founder** validating an idea before spending money.
- **Indie developer** who wants PM + eng-lead structure without hiring.
- **Privacy-sensitive builder** who cannot send product ideas to a cloud LLM.

## 4. Non-Goals

- Not a hosted SaaS product. Not multi-tenant. Not a real-time chat UI (CLI-first).
- Not a replacement for a real CA/CS/lawyer — `LegalFlags.ca_cs_lawyer_required`
  exists specifically to route users to a human professional when needed.

## 5. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | System accepts a natural-language product idea and produces a `ProductConstraints` JSON object. |
| FR-002 | Orchestrator dispatches `ProductConstraints` to all 5 worker agents concurrently. |
| FR-003 | Each worker agent returns output strictly conforming to its Pydantic schema. |
| FR-004 | GTM agent grounds all sentiment/market claims in scraped web, video, or social data — never invents statistics. |
| FR-005 | Legal/Finance agent flags India DPDP Act 2023, GST, and IT Act risks, plus a boolean `ca_cs_lawyer_required`. |
| FR-006 | All agent outputs pass a 2-layer review gate (schema + LLM rubric) before being shown to the user. |
| FR-007 | Failing outputs trigger a bounded repair loop (max 3 iterations) before surfacing a failure to the user. |
| FR-008 | Destructive local commands (`rm -rf`, force-push, push-to-main) are intercepted before execution. |
| FR-009 | Agent execution loops are capped at 5 iterations with duplicate-call detection. |
| FR-010 | System runs end-to-end with zero required paid API keys. |

## 6. MVP Feature Matrix

| Feature | MVP | Post-MVP |
|---|---|---|
| CLI single-idea run | ✅ | |
| 5 parallel worker agents | ✅ | |
| Web/video/social scraping | ✅ | |
| 2-layer review gate | ✅ | |
| Repair loop | ✅ | |
| Strands Evals diagnostics | ✅ | |
| Context compaction | ✅ | |
| Multi-turn conversational refinement | | ✅ |
| Web UI | | ✅ |

## 7. Success Criteria

- A user can run one CLI command and receive all 5 structured deliverables with
  zero cloud calls and zero paid subscriptions.
- No agent output reaches the user without passing the review gate.
- No destructive git/shell command executes without interception.
