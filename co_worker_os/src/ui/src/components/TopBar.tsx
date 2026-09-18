import { Globe2, MapPinned, Moon, Sun } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { OllamaStatus, Region } from '@/api'

interface TopBarProps {
  ollamaStatus: OllamaStatus
  region: Region
  onRegionChange: (region: Region) => void
  theme: 'dark' | 'light'
  onThemeToggle: () => void
  contextTokensUsed: number
  contextTokenBudget: number
}

const APP_VERSION = 'v0.1 Local' // matches pyproject.toml's co-worker-os version

/** The connection dot + model chip + token budget bar together form the
 * "Agentic Trust Stack" strip from the design brief: at a glance, is the
 * local model actually reachable, which one, and how much context is left. */
export function TopBar({
  ollamaStatus,
  region,
  onRegionChange,
  theme,
  onThemeToggle,
  contextTokensUsed,
  contextTokenBudget,
}: TopBarProps) {
  const primaryModel = ollamaStatus.availableModels[0]
  const tokenPct = Math.min(100, (contextTokensUsed / contextTokenBudget) * 100)

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center justify-between gap-4 border-b border-border-hairline bg-canvas/80 px-6 backdrop-blur-md">
      {/* Left: brand */}
      <div className="flex shrink-0 items-center gap-2.5">
        <span className="font-display text-lg font-bold tracking-tight text-text-primary">CO-WORKER</span>
        <span className="text-mono-tag rounded-md border border-border-hairline px-1.5 py-0.5 text-text-muted">
          {APP_VERSION}
        </span>
      </div>

      {/* Center: trust stack */}
      <div className="flex min-w-0 flex-1 items-center justify-center gap-4">
        <div className="flex shrink-0 items-center gap-2" title={ollamaStatus.baseUrl}>
          <span className="relative flex h-2 w-2">
            {ollamaStatus.connected && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-verdict-viable opacity-75" />
            )}
            <span
              className={cn(
                'relative inline-flex h-2 w-2 rounded-full',
                ollamaStatus.connected ? 'bg-verdict-viable' : 'bg-verdict-unviable',
              )}
            />
          </span>
          <span className="text-sm text-text-secondary">{ollamaStatus.connected ? 'Connected' : 'Disconnected'}</span>
        </div>

        {primaryModel && (
          <span className="text-mono-tag shrink-0 rounded-md border border-border-hairline bg-surface px-2 py-1 text-text-secondary">
            {primaryModel}
          </span>
        )}

        <div className="hidden min-w-32 flex-1 max-w-56 items-center gap-2 sm:flex">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface">
            <div
              className="h-full rounded-full bg-dept-pm transition-all duration-200"
              style={{ width: `${tokenPct}%` }}
            />
          </div>
          <span className="text-mono-tag shrink-0 text-text-muted">
            {contextTokensUsed.toLocaleString()} / {contextTokenBudget.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Right: region toggle + theme */}
      <div className="flex shrink-0 items-center gap-3">
        <div className="flex items-center rounded-lg border border-border-hairline bg-surface p-0.5" role="group" aria-label="Region focus">
          <RegionButton
            active={region === 'india'}
            onClick={() => onRegionChange('india')}
            icon={<MapPinned className="h-3.5 w-3.5" />}
            label="India-First"
          />
          <RegionButton
            active={region === 'global'}
            onClick={() => onRegionChange('global')}
            icon={<Globe2 className="h-3.5 w-3.5" />}
            label="Global-Aware"
          />
        </div>

        <button
          type="button"
          onClick={onThemeToggle}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-hairline bg-surface text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </header>
  )
}

function RegionButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors duration-150',
        active ? 'bg-dept-pm text-white' : 'text-text-secondary hover:text-text-primary',
      )}
    >
      {icon}
      <span className="hidden md:inline">{label}</span>
    </button>
  )
}
