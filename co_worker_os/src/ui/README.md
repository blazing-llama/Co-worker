# Co-Worker — Founder Command Center (Frontend)

Vite + React + TypeScript + Tailwind CSS v4 dashboard for the Co-Worker
multi-agent system, following the "Quiet Power" design brief in
`docs/ImplementationPlan.md`.

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

## Structure

```
src/ui/src/
├── api.ts                # Backend client (checkOllamaStatus, runCoWorkerTeam)
├── App.tsx                # Layout shell, theme + Ollama status + run state
├── index.css               # Tailwind v4 @theme tokens, base styles, subgrid utility
├── styles/theme.css        # Dark/light CSS custom properties
├── components/
│   ├── TopBar.tsx           # HUD header: status, model chip, region toggle
│   ├── InputConsole.tsx     # Prompt textarea, category chips, run button
│   └── tabs/                # (Phase 3) departmental workspace tabs
└── lib/utils.ts             # cn() class-merging helper
```

## Status

Phase 1 (design tokens, shell, TopBar, InputConsole, real API wiring to
`src/server.py`) is complete — see `docs/ImplementationPlan.md`'s frontend
phase log for what's built vs. still ahead (Shark Tank bento hero, 4
departmental tabs, diagnostics drawer).
