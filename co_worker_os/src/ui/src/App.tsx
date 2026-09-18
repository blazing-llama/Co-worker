import { useCallback, useEffect, useState } from 'react'
import { TopBar } from '@/components/TopBar'
import { InputConsole, type Category } from '@/components/InputConsole'
import { SharkTankHero } from '@/components/SharkTankHero'
import { ApiError, checkOllamaStatus, runCoWorkerTeam, type OllamaStatus, type Region, type RunTeamResponse } from '@/api'
import type { SharkTankVerdict } from '@/types'

const THEME_STORAGE_KEY = 'co-worker-theme'
const CONTEXT_TOKEN_BUDGET = 128_000
const OLLAMA_POLL_INTERVAL_MS = 5000

function getInitialTheme(): 'dark' | 'light' {
  const stored = localStorage.getItem(THEME_STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  return 'dark' // spec: dark ("Midnight Command Canvas") is the default
}

export default function App() {
  const [theme, setTheme] = useState<'dark' | 'light'>(getInitialTheme)
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus>({
    connected: false,
    baseUrl: 'http://localhost:11434/v1',
    availableModels: [],
    routing: {},
  })
  const [region, setRegion] = useState<Region>('india')
  const [prompt, setPrompt] = useState('')
  const [category, setCategory] = useState<Category | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [result, setResult] = useState<RunTeamResponse | null>(null)
  const [runError, setRunError] = useState<string | null>(null)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem(THEME_STORAGE_KEY, theme)
  }, [theme])

  useEffect(() => {
    let cancelled = false
    async function poll() {
      const status = await checkOllamaStatus()
      if (!cancelled) setOllamaStatus(status)
    }
    poll()
    const id = setInterval(poll, OLLAMA_POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  const handleRun = useCallback(async () => {
    if (!prompt.trim() || isRunning) return
    setIsRunning(true)
    setRunError(null)
    setResult(null)
    try {
      const response = await runCoWorkerTeam({ prompt, category: category ?? undefined, region })
      setResult(response)
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : 'Unexpected error running the Co-Worker team.')
    } finally {
      setIsRunning(false)
    }
  }, [prompt, category, region, isRunning])

  return (
    <div className="min-h-screen bg-canvas font-body text-text-primary">
      <TopBar
        ollamaStatus={ollamaStatus}
        region={region}
        onRegionChange={setRegion}
        theme={theme}
        onThemeToggle={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
        contextTokensUsed={0}
        contextTokenBudget={CONTEXT_TOKEN_BUDGET}
      />

      <main className="mx-auto grid max-w-[1600px] grid-cols-12 gap-5 p-6">
        <InputConsole
          value={prompt}
          onChange={setPrompt}
          category={category}
          onCategoryChange={setCategory}
          onRun={handleRun}
          isRunning={isRunning}
          runStep={null}
        />

        {!ollamaStatus.connected && (
          <div className="card-hairline col-span-12 rounded-[var(--radius-outer)] bg-surface p-4 text-sm text-verdict-pivot">
            Ollama isn't reachable at {ollamaStatus.baseUrl}. Start it locally (and pull the routed models) before
            running the team — see README.md Quick Start.
          </div>
        )}

        {runError && (
          <div className="card-hairline col-span-12 rounded-[var(--radius-outer)] bg-surface p-4 text-sm text-verdict-unviable">
            {runError}
          </div>
        )}

        {result?.outputs.cofounder && (
          <SharkTankHero
            verdict={result.outputs.cofounder as unknown as SharkTankVerdict}
            region={(result.constraints.region as Region) ?? region}
          />
        )}

        {/* Zone 4 (departmental tabs) and Zone 5 (diagnostics drawer) land in
            later phases. This raw preview covers the other 4 agents' output
            in the meantime, so nothing the backend returns is hidden. */}
        {result && (
          <details className="card-hairline col-span-12 rounded-[var(--radius-outer)] bg-surface p-4">
            <summary className="cursor-pointer text-sm font-medium text-text-secondary">
              Other agent outputs (raw preview — departmental tabs coming in Phase F3)
            </summary>
            <pre className="mt-3 max-h-[500px] overflow-auto font-mono text-xs text-text-secondary">
              {JSON.stringify(
                { product_manager: result.outputs.product_manager, engineer: result.outputs.engineer, gtm_ops: result.outputs.gtm_ops, legal_finance: result.outputs.legal_finance },
                null,
                2,
              )}
            </pre>
          </details>
        )}
      </main>
    </div>
  )
}
