import { useEffect, useMemo, useRef } from 'react'
import { AlertCircle, ChevronUp, Loader2, Search, Terminal } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { DiagnoseResponse, StreamEvent } from '@/api'

export type RunStatus = 'idle' | 'running' | 'done' | 'error'

interface DiagnosticDrawerProps {
  isOpen: boolean
  onToggle: () => void
  status: RunStatus
  events: StreamEvent[]
  canDiagnose: boolean
  isDiagnosing: boolean
  diagnosis: DiagnoseResponse | null
  onRunDiagnostics: () => void
}

const STATUS_META: Record<RunStatus, { label: string; color: string }> = {
  idle: { label: 'Idle', color: 'var(--text-muted)' },
  running: { label: 'Running', color: 'var(--dept-pm)' },
  done: { label: 'Done', color: 'var(--verdict-viable)' },
  error: { label: 'Error', color: 'var(--verdict-unviable)' },
}

const EVENT_COLOR: Record<string, string> = {
  run_start: 'var(--text-secondary)',
  parse_start: 'var(--text-secondary)',
  parse_done: 'var(--dept-pm)',
  chat_call_start: 'var(--text-muted)',
  chat_call_end: 'var(--text-muted)',
  agent_start: 'var(--dept-eng)',
  agent_done: 'var(--verdict-viable)',
  agent_failed: 'var(--verdict-unviable)',
  checkpoint_pending: 'var(--dept-legal)',
  checkpoint_result: 'var(--dept-legal)',
  run_done: 'var(--verdict-viable)',
  run_error: 'var(--verdict-unviable)',
}

function formatEventLine(event: StreamEvent): string {
  const { type, data } = event
  switch (type) {
    case 'run_start':
      return 'Run started'
    case 'parse_start':
      return 'Parsing constraints from prompt…'
    case 'parse_done':
      return 'Constraints parsed'
    case 'chat_call_start':
      return `${data.agent} (${data.role}) → model call started`
    case 'chat_call_end':
      return `${data.agent} (${data.role}) → model call finished (${data.duration_ms}ms)`
    case 'agent_start':
      return `${data.agent} → dispatched`
    case 'agent_done':
      return `${data.agent} → done in ${data.iterations} attempt(s), rubric ${Number(data.rubric_score).toFixed(2)}`
    case 'agent_failed':
      return `${data.agent} → repair loop exhausted`
    case 'checkpoint_pending':
      return `${data.agent} → awaiting human checkpoint`
    case 'checkpoint_result':
      return `${data.agent} → checkpoint ${data.approved ? 'approved' : 'DENIED'}`
    case 'run_done':
      return 'Run complete'
    case 'run_error':
      return `Run error: ${data.detail ?? data.reason}`
    default:
      return type
  }
}

/**
 * Zone 5. Repair-loop attempt counters come from real `agent_done` events'
 * `iterations` field. "Timings" are real wall-clock call durations
 * (`chat_call_end`'s `duration_ms`, measured server-side) -- NOT token
 * consumption. src/core/ollama_client.py never requests/parses token usage
 * from Ollama's response, so a token-rate readout would be fabricated;
 * duration is the honest signal actually available.
 */
export function DiagnosticDrawer({
  isOpen,
  onToggle,
  status,
  events,
  canDiagnose,
  isDiagnosing,
  diagnosis,
  onRunDiagnostics,
}: DiagnosticDrawerProps) {
  const logRef = useRef<HTMLDivElement>(null)
  const meta = STATUS_META[status]

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [events])

  useEffect(() => {
    if (!isOpen) return
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onToggle()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onToggle])

  const iterationsByAgent = useMemo(() => {
    const map: Record<string, { iterations: number; passed: boolean; rubricScore: number }> = {}
    for (const event of events) {
      if (event.type === 'agent_done') {
        map[String(event.data.agent)] = {
          iterations: Number(event.data.iterations),
          passed: Boolean(event.data.passed),
          rubricScore: Number(event.data.rubric_score),
        }
      }
    }
    return map
  }, [events])

  const callDurations = useMemo(
    () => events.filter((e) => e.type === 'chat_call_end').map((e) => Number(e.data.duration_ms)),
    [events],
  )
  const totalCallMs = callDurations.reduce((sum, ms) => sum + ms, 0)

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 border-t border-border-hairline bg-surface">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        className="flex h-10 w-full items-center gap-3 px-6 text-sm text-text-secondary transition-colors hover:text-text-primary"
      >
        <Terminal className="h-4 w-4 shrink-0" />
        <span className="font-medium">Strands Evals Diagnostics &amp; Trace Logs</span>
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: meta.color }} />
          <span className="text-mono-tag normal-case tracking-normal" style={{ color: meta.color }}>
            {meta.label}
          </span>
        </span>
        <ChevronUp className={cn('ml-auto h-4 w-4 shrink-0 transition-transform duration-200', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <div className="grid h-80 grid-cols-12 gap-0 border-t border-border-hairline">
          <div ref={logRef} className="col-span-8 overflow-y-auto border-r border-border-hairline p-4 font-mono text-xs">
            {events.length === 0 && <p className="text-text-muted">No events yet — run the team to see a live trace.</p>}
            {events.map((event, i) => (
              <div key={i} className="mb-1 flex gap-2">
                <span style={{ color: EVENT_COLOR[event.type] ?? 'var(--text-muted)' }}>●</span>
                <span className="text-text-secondary">{formatEventLine(event)}</span>
              </div>
            ))}
          </div>

          <div className="col-span-4 overflow-y-auto p-4">
            <h4 className="text-mono-tag mb-2 text-text-muted">Repair Loop Attempts</h4>
            <div className="mb-4 space-y-1">
              {Object.entries(iterationsByAgent).map(([agent, info]) => (
                <div key={agent} className="flex items-center justify-between text-xs">
                  <span className="text-text-secondary">{agent}</span>
                  <span className={info.passed ? 'text-verdict-viable' : 'text-verdict-unviable'}>
                    {info.iterations}× · {info.rubricScore.toFixed(2)}
                  </span>
                </div>
              ))}
              {Object.keys(iterationsByAgent).length === 0 && <p className="text-xs text-text-muted">No agents finished yet.</p>}
            </div>

            <h4 className="text-mono-tag mb-2 text-text-muted">Model Call Durations</h4>
            <p className="mb-4 text-xs text-text-secondary">
              {callDurations.length} call(s), {totalCallMs.toLocaleString()}ms total
            </p>

            <h4 className="text-mono-tag mb-2 text-text-muted">Strands Evals Diagnosis</h4>
            <button
              type="button"
              onClick={onRunDiagnostics}
              disabled={!canDiagnose || isDiagnosing}
              className="mb-2 flex items-center gap-1.5 rounded-[var(--radius-inner)] border border-border-hairline bg-canvas/40 px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isDiagnosing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
              Run Diagnostics
            </button>

            {diagnosis && (
              <div className="text-xs">
                {!diagnosis.available ? (
                  <div className="flex items-start gap-1.5 text-verdict-pivot">
                    <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span>Diagnosis unavailable: {diagnosis.error}</span>
                  </div>
                ) : diagnosis.failures.length === 0 ? (
                  <p className="text-verdict-viable">No failures detected.</p>
                ) : (
                  <div className="space-y-2">
                    <div>
                      <div className="text-mono-tag mb-1 text-verdict-unviable">Failures</div>
                      <ul className="list-inside list-disc space-y-0.5 text-text-secondary">
                        {diagnosis.failures.map((f, i) => (
                          <li key={i}>{f}</li>
                        ))}
                      </ul>
                    </div>
                    {diagnosis.root_causes.length > 0 && (
                      <div>
                        <div className="text-mono-tag mb-1 text-dept-legal">Root Causes</div>
                        <ul className="list-inside list-disc space-y-0.5 text-text-secondary">
                          {diagnosis.root_causes.map((rc, i) => (
                            <li key={i}>{rc}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
