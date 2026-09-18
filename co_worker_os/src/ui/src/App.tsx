import { useCallback, useEffect, useRef, useState } from 'react'
import { TopBar } from '@/components/TopBar'
import { InputConsole, type Category } from '@/components/InputConsole'
import { SharkTankHero } from '@/components/SharkTankHero'
import { WorkspaceTabs } from '@/components/WorkspaceTabs'
import { DiagnosticDrawer, type RunStatus } from '@/components/DiagnosticDrawer'
import {
  checkOllamaStatus,
  diagnoseRun,
  streamRunTeam,
  type DiagnoseResponse,
  type OllamaStatus,
  type Region,
  type RunTeamResponse,
  type StreamEvent,
} from '@/api'
import type { GTMSentiment, LegalFlags, PRDSpec, SharkTankVerdict, TechStackSpec } from '@/types'

const THEME_STORAGE_KEY = 'co-worker-theme'
const CONTEXT_TOKEN_BUDGET = 128_000
const OLLAMA_POLL_INTERVAL_MS = 5000

function getInitialTheme(): 'dark' | 'light' {
  const stored = localStorage.getItem(THEME_STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  return 'dark' // spec: dark ("Midnight Command Canvas") is the default
}

function latestRunStep(events: StreamEvent[]): string | null {
  const last = events[events.length - 1]
  if (!last) return null
  if (last.type === 'agent_start') return `Dispatching ${last.data.agent}…`
  if (last.type === 'agent_done') return `${last.data.agent} done…`
  if (last.type === 'chat_call_start') return `${last.data.agent} thinking…`
  return null
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

  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [runStatus, setRunStatus] = useState<RunStatus>('idle')
  const [streamEvents, setStreamEvents] = useState<StreamEvent[]>([])
  const [diagnosis, setDiagnosis] = useState<DiagnoseResponse | null>(null)
  const [isDiagnosing, setIsDiagnosing] = useState(false)
  const closeStreamRef = useRef<(() => void) | null>(null)

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

  useEffect(() => () => closeStreamRef.current?.(), [])

  const handleRun = useCallback(() => {
    if (!prompt.trim() || isRunning) return
    closeStreamRef.current?.()

    setIsRunning(true)
    setRunStatus('running')
    setRunError(null)
    setResult(null)
    setStreamEvents([])
    setDiagnosis(null)

    closeStreamRef.current = streamRunTeam(
      { prompt, category: category ?? undefined, region },
      {
        onEvent: (event) => setStreamEvents((prev) => [...prev, event]),
        onResult: (response) => {
          setResult(response)
          setRunStatus('done')
          setIsRunning(false)
        },
        onError: (message) => {
          setRunError(message)
          setRunStatus('error')
          setIsRunning(false)
        },
      },
    )
  }, [prompt, category, region, isRunning])

  const handleRunDiagnostics = useCallback(async () => {
    if (!result || isDiagnosing) return
    setIsDiagnosing(true)
    try {
      const diagnosis = await diagnoseRun(result.run_id, result.call_records)
      setDiagnosis(diagnosis)
    } catch {
      setDiagnosis({ run_id: result.run_id, available: false, failures: [], root_causes: [], error: 'Diagnose request failed.' })
    } finally {
      setIsDiagnosing(false)
    }
  }, [result, isDiagnosing])

  return (
    <div className="min-h-screen bg-canvas pb-10 font-body text-text-primary">
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
          runStep={latestRunStep(streamEvents)}
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

        {result?.outputs.product_manager && result.outputs.engineer && result.outputs.gtm_ops && result.outputs.legal_finance && (
          <WorkspaceTabs
            pm={result.outputs.product_manager as unknown as PRDSpec}
            eng={result.outputs.engineer as unknown as TechStackSpec}
            gtm={result.outputs.gtm_ops as unknown as GTMSentiment}
            legal={result.outputs.legal_finance as unknown as LegalFlags}
            region={(result.constraints.region as Region) ?? region}
          />
        )}
      </main>

      <DiagnosticDrawer
        isOpen={isDrawerOpen}
        onToggle={() => setIsDrawerOpen((open) => !open)}
        status={runStatus}
        events={streamEvents}
        canDiagnose={result != null}
        isDiagnosing={isDiagnosing}
        diagnosis={diagnosis}
        onRunDiagnostics={handleRunDiagnostics}
      />
    </div>
  )
}
