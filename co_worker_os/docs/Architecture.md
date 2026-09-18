# Architecture — Hub-and-Spoke Multi-Agent Blueprint

## Topology

```
                      ┌─────────────────┐
        NL prompt --> │  Orchestrator    │  (Hub)
                      │  - parses to     │
                      │  ProductConstraints
                      └────────┬─────────┘
                               │ (read-only, dispatched concurrently)
         ┌──────────┬──────────┼──────────┬──────────┐
         ▼          ▼          ▼          ▼          ▼
     CoFounder      PM       Engineer    GTM/Ops   Legal/Finance
   (SharkTank    (PRDSpec) (TechStackSpec)(GTMSentiment)(LegalFlags)
    Verdict)
         │          │          │          │          │
         └──────────┴──────────┼──────────┴──────────┘
                                ▼
                      2-Layer Review Gate
                   (Schema check -> LLM rubric)
                                │
                     pass ──────┴────── fail (<=3 repairs)
                      │                      │
                      ▼                      ▼
               Formatted Output      Repair loop back to
                to user                  originating agent
```

## Key Design Rules

- **Hub owns parsing.** Only the Orchestrator ever reads the raw user prompt.
  Workers consume `ProductConstraints` exclusively, so no worker can drift from a
  re-interpretation of ambiguous free text.
- **Concurrency, not sequence.** The 5 workers run in parallel (LangGraph
  `.parallel()` edges) — none depends on another's output. Cross-agent debate (e.g.
  Co-Founder vs. Engineer feasibility disagreement) happens in the review layer via
  AG2 group-chat patterns, not in the dispatch graph.
- **Human checkpoint before Legal/Finance is surfaced.** `interrupt_before` pauses
  execution so a human can review before any `ca_cs_lawyer_required` flag or legal
  claim reaches the final output.
- **All model calls go through `http://localhost:11434/v1`.** No component holds a
  cloud LLM client.
- **Grounding boundary.** GTM/Research claims must trace to scraper output
  (`src/scrapers/`); the review gate's Layer 2 rubric explicitly checks this.

## Data Flow Contracts

Every arrow above is a Pydantic model from `src/core/schemas.py` — never a raw
string. See `docs/PRD.md` §5 for the requirement each contract satisfies.
