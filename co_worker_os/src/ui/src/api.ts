/**
 * Client API layer for the local Python backend (src/server.py, FastAPI) and
 * its proxied Ollama status. Every call degrades gracefully (returns a safe
 * fallback shape) rather than throwing an unhandled rejection into a React
 * render — the backend/Ollama being down is an expected state, not a crash.
 */

export type Region = 'india' | 'global'

export interface OllamaStatus {
  connected: boolean
  baseUrl: string
  availableModels: string[]
  routing: Record<string, boolean>
}

export interface RunTeamRequest {
  prompt: string
  category?: string
  region?: Region
}

export interface ReviewReport {
  schema_check_passed: boolean
  llm_rubric_score: number
  passed: boolean
  repair_hints: { failed_checks: string[]; suggested_fix: string } | null
}

export interface CallRecord {
  agent_name: string // "<agent>:<role>", role is "parse" | "generate" | "review"
  system_prompt: string
  user_prompt: string
  response: string
  start_time: string
  end_time: string
}

export interface RunTeamResponse {
  run_id: string
  constraints: Record<string, unknown>
  outputs: Record<string, Record<string, unknown>>
  reports: Record<string, ReviewReport>
  iterations: Record<string, number>
  formatted_output: string
  call_records: CallRecord[]
}

export interface DiagnoseResponse {
  run_id: string
  available: boolean
  failures: string[]
  root_causes: string[]
  error: string | null
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

const OLLAMA_STATUS_FALLBACK: OllamaStatus = {
  connected: false,
  baseUrl: 'http://localhost:11434/v1',
  availableModels: [],
  routing: {},
}

/** Pings the backend's /api/ollama-status (which itself checks the local
 * Ollama daemon). Never throws -- a network failure here means "backend not
 * up yet," which the TopBar renders as disconnected, not a broken page. */
export async function checkOllamaStatus(): Promise<OllamaStatus> {
  try {
    const res = await fetch('/api/ollama-status')
    if (!res.ok) return OLLAMA_STATUS_FALLBACK
    const body = await res.json()
    return {
      connected: body.connected,
      baseUrl: body.base_url,
      availableModels: body.available_models,
      routing: body.routing,
    }
  } catch {
    return OLLAMA_STATUS_FALLBACK
  }
}

/** Runs the 5-agent pipeline. Unlike checkOllamaStatus, this DOES throw
 * (ApiError) on failure -- a run failing is action-worthy (show the user why),
 * not something to silently swallow behind a fallback. */
export async function runCoWorkerTeam(payload: RunTeamRequest): Promise<RunTeamResponse> {
  const res = await fetch('/api/run-team', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // response wasn't JSON; keep statusText
    }
    throw new ApiError(res.status, detail)
  }

  return res.json()
}

export interface StreamEvent {
  type: string
  data: Record<string, unknown>
}

const TERMINAL_STREAM_EVENTS = new Set(['result', 'run_error'])

/**
 * Streams a run via GET /api/run-team/stream (Server-Sent Events) instead of
 * waiting for the single POST /api/run-team response. Backs the diagnostics
 * drawer's live log -- every named backend event (chat_call_start/end,
 * agent_start/done, checkpoint_*, etc.) is forwarded via `onEvent` as it
 * arrives, not buffered until the run finishes.
 *
 * Returns a cleanup function to close the connection early (e.g. on
 * unmount). EventSource only supports GET, which is why this takes query
 * params rather than a JSON body like runCoWorkerTeam.
 */
export function streamRunTeam(
  payload: RunTeamRequest,
  handlers: {
    onEvent: (event: StreamEvent) => void
    onResult: (result: RunTeamResponse) => void
    onError: (message: string) => void
  },
): () => void {
  const params = new URLSearchParams({ prompt: payload.prompt })
  if (payload.category) params.set('category', payload.category)
  if (payload.region) params.set('region', payload.region)

  const source = new EventSource(`/api/run-team/stream?${params.toString()}`)

  const EVENT_TYPES = [
    'run_start',
    'parse_start',
    'parse_done',
    'chat_call_start',
    'chat_call_end',
    'agent_start',
    'agent_done',
    'agent_failed',
    'checkpoint_pending',
    'checkpoint_result',
    'run_done',
    'run_error',
    'result',
  ]

  for (const type of EVENT_TYPES) {
    source.addEventListener(type, (raw: MessageEvent) => {
      let data: Record<string, unknown>
      try {
        data = JSON.parse(raw.data)
      } catch {
        return
      }

      if (type === 'result') {
        handlers.onResult(data as unknown as RunTeamResponse)
        source.close()
        return
      }
      if (type === 'run_error') {
        const detail = typeof data.detail === 'string' ? data.detail : String(data.reason ?? 'Run failed')
        handlers.onError(detail)
        source.close()
        return
      }
      handlers.onEvent({ type, data })
      if (TERMINAL_STREAM_EVENTS.has(type)) source.close()
    })
  }

  source.onerror = () => {
    handlers.onError('Lost connection to the backend stream.')
    source.close()
  }

  return () => source.close()
}

/** Runs Strands Evals diagnosis over a completed run's call records. A
 * deliberate follow-up action, not automatic -- it's its own LLM-judge call.
 * Throws ApiError on transport failure; a successful response with
 * `available: false` (see DiagnoseResponse) means the backend genuinely
 * could not diagnose (e.g. no local model reachable) -- show that plainly,
 * never synthesize a fake diagnosis client-side. */
export async function diagnoseRun(runId: string, callRecords: CallRecord[]): Promise<DiagnoseResponse> {
  const res = await fetch('/api/diagnose', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id: runId, call_records: callRecords }),
  })
  if (!res.ok) {
    throw new ApiError(res.status, res.statusText)
  }
  return res.json()
}
