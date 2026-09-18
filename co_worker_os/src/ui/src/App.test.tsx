import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import * as api from '@/api'

vi.mock('@/api', async () => {
  const actual = await vi.importActual<typeof import('@/api')>('@/api')
  return {
    ...actual,
    checkOllamaStatus: vi.fn(),
    streamRunTeam: vi.fn(),
    diagnoseRun: vi.fn(),
  }
})

const mockedCheckOllamaStatus = vi.mocked(api.checkOllamaStatus)
const mockedStreamRunTeam = vi.mocked(api.streamRunTeam)

const disconnectedStatus: api.OllamaStatus = {
  connected: false,
  baseUrl: 'http://localhost:11434/v1',
  availableModels: [],
  routing: {},
}

beforeEach(() => {
  localStorage.clear()
  mockedCheckOllamaStatus.mockResolvedValue(disconnectedStatus)
  mockedStreamRunTeam.mockReturnValue(() => {})
})

describe('App: dark-mode styling', () => {
  it('defaults to the dark theme and sets data-theme on <html>', () => {
    render(<App />)
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('toggling the theme button flips document.documentElement.dataset.theme', async () => {
    const user = userEvent.setup()
    render(<App />)
    expect(document.documentElement.dataset.theme).toBe('dark')

    await user.click(screen.getByRole('button', { name: /switch to light mode/i }))
    expect(document.documentElement.dataset.theme).toBe('light')

    await user.click(screen.getByRole('button', { name: /switch to dark mode/i }))
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('persists the chosen theme to localStorage', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: /switch to light mode/i }))
    expect(localStorage.getItem('co-worker-theme')).toBe('light')
  })
})

describe('App: empty state', () => {
  it('shows the input console but no result sections before any run', () => {
    render(<App />)
    expect(screen.getByPlaceholderText(/describe your business idea/i)).toBeInTheDocument()
    expect(screen.queryByText('Product Risk — 4 Axes')).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: /pm workspace/i })).not.toBeInTheDocument()
    expect(screen.queryByTestId('run-skeleton')).not.toBeInTheDocument()
  })

  it('shows the Ollama-disconnected banner when the backend reports disconnected', async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByText(/ollama isn't reachable/i)).toBeInTheDocument())
  })

  it('does not show the Ollama-disconnected banner once connected', async () => {
    mockedCheckOllamaStatus.mockResolvedValue({ ...disconnectedStatus, connected: true })
    render(<App />)
    await waitFor(() => expect(mockedCheckOllamaStatus).toHaveBeenCalled())
    expect(screen.queryByText(/ollama isn't reachable/i)).not.toBeInTheDocument()
  })
})

describe('App: loading skeleton', () => {
  it('shows the run skeleton while a run is in flight and no result has landed yet', async () => {
    const user = userEvent.setup()
    // Never call onResult/onError -- simulates a run that's still streaming.
    mockedStreamRunTeam.mockReturnValue(() => {})
    render(<App />)

    await user.type(screen.getByPlaceholderText(/describe your business idea/i), 'an idea')
    await user.click(screen.getByRole('button', { name: /run co-worker team/i }))

    expect(screen.getByTestId('run-skeleton')).toBeInTheDocument()
  })

  it('replaces the skeleton with the result once the run completes', async () => {
    const user = userEvent.setup()
    let capturedHandlers: Parameters<typeof api.streamRunTeam>[1] | null = null
    mockedStreamRunTeam.mockImplementation((_payload, handlers) => {
      capturedHandlers = handlers
      return () => {}
    })

    render(<App />)
    await user.type(screen.getByPlaceholderText(/describe your business idea/i), 'an idea')
    await user.click(screen.getByRole('button', { name: /run co-worker team/i }))
    expect(screen.getByTestId('run-skeleton')).toBeInTheDocument()

    capturedHandlers!.onResult({
      run_id: 'r1',
      constraints: { region: 'india' },
      outputs: {
        cofounder: {
          tam_usd: 1,
          sam_usd: 1,
          unit_economics_summary: 'x',
          defensibility_notes: 'x',
          risks: [
            { category: 'value', description: 'd', severity: 'low' },
            { category: 'usability', description: 'd', severity: 'low' },
            { category: 'feasibility', description: 'd', severity: 'low' },
            { category: 'viability', description: 'd', severity: 'low' },
          ],
          verdict_confidence: 'high',
        },
      },
      reports: {},
      iterations: {},
      formatted_output: 'x',
      call_records: [],
    })

    await waitFor(() => expect(screen.queryByTestId('run-skeleton')).not.toBeInTheDocument())
    expect(screen.getByText('Product Risk — 4 Axes')).toBeInTheDocument()
  })
})

describe('App: error alert banner', () => {
  it('shows the error banner and hides the skeleton when the stream reports an error', async () => {
    const user = userEvent.setup()
    let capturedHandlers: Parameters<typeof api.streamRunTeam>[1] | null = null
    mockedStreamRunTeam.mockImplementation((_payload, handlers) => {
      capturedHandlers = handlers
      return () => {}
    })

    render(<App />)
    await user.type(screen.getByPlaceholderText(/describe your business idea/i), 'an idea')
    await user.click(screen.getByRole('button', { name: /run co-worker team/i }))
    expect(screen.getByTestId('run-skeleton')).toBeInTheDocument()

    capturedHandlers!.onError('Ollama is unreachable.')

    await waitFor(() => expect(screen.getByText('Ollama is unreachable.')).toBeInTheDocument())
    expect(screen.queryByTestId('run-skeleton')).not.toBeInTheDocument()
  })

  it('clears a previous error banner when a new run starts', async () => {
    const user = userEvent.setup()
    let capturedHandlers: Parameters<typeof api.streamRunTeam>[1] | null = null
    mockedStreamRunTeam.mockImplementation((_payload, handlers) => {
      capturedHandlers = handlers
      return () => {}
    })

    render(<App />)
    const textarea = screen.getByPlaceholderText(/describe your business idea/i)
    const runButton = screen.getByRole('button', { name: /run co-worker team/i })

    await user.type(textarea, 'an idea')
    await user.click(runButton)
    capturedHandlers!.onError('first failure')
    await waitFor(() => expect(screen.getByText('first failure')).toBeInTheDocument())

    await user.click(runButton)
    expect(screen.queryByText('first failure')).not.toBeInTheDocument()
  })
})
