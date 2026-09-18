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

export interface RunTeamResponse {
  run_id: string
  constraints: Record<string, unknown>
  outputs: Record<string, Record<string, unknown>>
  reports: Record<string, ReviewReport>
  iterations: Record<string, number>
  formatted_output: string
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
