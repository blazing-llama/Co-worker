import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TopBar } from '@/components/TopBar'
import type { OllamaStatus } from '@/api'

const connectedStatus: OllamaStatus = {
  connected: true,
  baseUrl: 'http://localhost:11434/v1',
  availableModels: ['qwen2.5:32b'],
  routing: { 'qwen2.5:32b': true },
}

const disconnectedStatus: OllamaStatus = {
  connected: false,
  baseUrl: 'http://localhost:11434/v1',
  availableModels: [],
  routing: {},
}

function renderTopBar(overrides: Partial<React.ComponentProps<typeof TopBar>> = {}) {
  const props: React.ComponentProps<typeof TopBar> = {
    ollamaStatus: connectedStatus,
    region: 'india',
    onRegionChange: vi.fn(),
    theme: 'dark',
    onThemeToggle: vi.fn(),
    contextTokensUsed: 0,
    contextTokenBudget: 128_000,
    ...overrides,
  }
  return { ...render(<TopBar {...props} />), props }
}

describe('TopBar rendering', () => {
  it('renders the brand and version pill', () => {
    renderTopBar()
    expect(screen.getByText('CO-WORKER')).toBeInTheDocument()
    expect(screen.getByText(/v0\.1 Local/i)).toBeInTheDocument()
  })

  it('shows Connected when Ollama is reachable', () => {
    renderTopBar({ ollamaStatus: connectedStatus })
    expect(screen.getByText('Connected')).toBeInTheDocument()
    expect(screen.getByText('qwen2.5:32b')).toBeInTheDocument()
  })

  it('shows Disconnected and no model chip when Ollama is unreachable', () => {
    renderTopBar({ ollamaStatus: disconnectedStatus })
    expect(screen.getByText('Disconnected')).toBeInTheDocument()
    expect(screen.queryByText('qwen2.5:32b')).not.toBeInTheDocument()
  })

  it('renders the token budget as provided', () => {
    renderTopBar({ contextTokensUsed: 4120, contextTokenBudget: 128_000 })
    expect(screen.getByText('4,120 / 128,000')).toBeInTheDocument()
  })
})

describe('TopBar theme toggle (dark/light)', () => {
  it('shows a Sun icon (switch-to-light affordance) when theme is dark', () => {
    renderTopBar({ theme: 'dark' })
    expect(screen.getByRole('button', { name: /switch to light mode/i })).toBeInTheDocument()
  })

  it('shows a Moon icon (switch-to-dark affordance) when theme is light', () => {
    renderTopBar({ theme: 'light' })
    expect(screen.getByRole('button', { name: /switch to dark mode/i })).toBeInTheDocument()
  })

  it('calls onThemeToggle when the theme button is clicked', async () => {
    const user = userEvent.setup()
    const { props } = renderTopBar({ theme: 'dark' })
    await user.click(screen.getByRole('button', { name: /switch to light mode/i }))
    expect(props.onThemeToggle).toHaveBeenCalledTimes(1)
  })
})

describe('TopBar region toggle', () => {
  it('marks the active region button as pressed', () => {
    renderTopBar({ region: 'india' })
    expect(screen.getByRole('button', { name: /india-first/i })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /global-aware/i })).toHaveAttribute('aria-pressed', 'false')
  })

  it('calls onRegionChange with the clicked region', async () => {
    const user = userEvent.setup()
    const { props } = renderTopBar({ region: 'india' })
    await user.click(screen.getByRole('button', { name: /global-aware/i }))
    expect(props.onRegionChange).toHaveBeenCalledWith('global')
  })
})
