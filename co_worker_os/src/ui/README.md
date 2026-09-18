# Co-Worker — Founder Command Center (Frontend)

Vite + React + TypeScript + Tailwind CSS v4 dashboard for the Co-Worker
multi-agent system, following the "Quiet Power" design brief in
`docs/ImplementationPlan.md`. Desktop-only by design — not a responsive site.

## Run locally

```bash
# 1. Backend (from co_worker_os/, in a separate terminal, with the venv active)
uvicorn src.server:app --reload

# 2. Frontend
npm install
npm run dev
```

Vite proxies `/api/*` to `http://127.0.0.1:8000` (see `vite.config.ts`), so the
dev server expects the backend already running there.

## Testing

```bash
npm test         # one-shot (vitest run) -- what CI/regression checks mean
npm run test:watch  # interactive watch mode
```

Every test mocks `src/api.ts` — no backend or Ollama needs to be running to
run the suite.

## Structure

```
src/ui/src/
├── api.ts                     # Backend client (checkOllamaStatus, runCoWorkerTeam, streamRunTeam, diagnoseRun)
├── types.ts                   # TS mirrors of src/core/schemas.py's Pydantic contracts
├── App.tsx                     # Layout shell, theme + Ollama status + run state
├── App.test.tsx                # Empty state / loading skeleton / error banner / dark-mode tests
├── index.css                    # Tailwind v4 @theme tokens, base styles, subgrid utility
├── styles/theme.css              # Dark/light CSS custom properties
├── test/
│   ├── setup.ts                   # jest-dom matchers, per-test cleanup
│   └── fixtures.ts                 # Shared Pydantic-schema-shaped test fixtures
├── components/
│   ├── TopBar.tsx                   # HUD header: status, model chip, region toggle
│   ├── InputConsole.tsx             # Prompt textarea, category chips, run button
│   ├── SharkTankHero.tsx            # Verdict banner + 4-axis risk gauges (Zone 3)
│   ├── RiskGauge.tsx                # Single risk gauge (category, severity, tooltip)
│   ├── RunSkeleton.tsx              # Loading placeholder while a run is in flight
│   ├── WorkspaceTabs.tsx            # Departmental tabs container (Zone 4)
│   ├── DiagnosticDrawer.tsx         # Live SSE log + Strands Evals diagnosis (Zone 5)
│   ├── tabs/                        # PM / Engineering / GTM / Legal tab content
│   ├── ui/tags.tsx                  # Shared ConfidenceTag / MonoIdTag
│   └── __tests__/                   # Component regression tests (Vitest + RTL)
└── lib/utils.ts                 # cn() class-merging helper
```

## Status

All 4 frontend phases (F1–F4) from the original design brief are complete —
see `docs/ImplementationPlan.md`'s frontend phase log for what's built and
how each phase was verified, including the currency/risk-gauge refinements
and this test suite. No live-Ollama success-path run has been performed from
this development environment; see the plan doc's "Ollama Availability" notes.
