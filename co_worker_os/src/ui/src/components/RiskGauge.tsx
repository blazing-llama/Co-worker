import * as Tooltip from '@radix-ui/react-tooltip'
import { Target, TrendingUp, Users, Wrench } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ConfidenceLevel, ProductRisk, RiskCategory } from '@/types'

const CATEGORY_LABEL: Record<RiskCategory, string> = {
  value: 'Value Risk',
  usability: 'Usability Risk',
  feasibility: 'Feasibility Risk',
  viability: 'Viability Risk',
}

const CATEGORY_ICON: Record<RiskCategory, React.ComponentType<{ className?: string }>> = {
  value: Target,
  usability: Users,
  feasibility: Wrench,
  viability: TrendingUp,
}

// The backend (SharkTankVerdict.risks[].severity) only gives a categorical
// tier (high/medium/low), never a numeric confidence score. These percentages
// are a PRESENTATIONAL mapping for the radial gauge's fill -- not a number
// the model produced. The real, model-authored evidence is the
// `description` text, shown verbatim in the tooltip.
const SEVERITY_TO_GAUGE_PCT: Record<ConfidenceLevel, number> = {
  low: 25,
  medium: 60,
  high: 85,
}

const SEVERITY_COLOR: Record<ConfidenceLevel, string> = {
  low: 'var(--verdict-viable)',
  medium: 'var(--verdict-pivot)',
  high: 'var(--verdict-unviable)',
}

const SEVERITY_TAG_LABEL: Record<ConfidenceLevel, string> = {
  low: 'Low',
  medium: 'Med',
  high: 'High',
}

interface RiskGaugeProps {
  risk: ProductRisk
}

const RADIUS = 26
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export function RiskGauge({ risk }: RiskGaugeProps) {
  const Icon = CATEGORY_ICON[risk.category]
  const pct = SEVERITY_TO_GAUGE_PCT[risk.severity]
  const color = SEVERITY_COLOR[risk.severity]
  const dashOffset = CIRCUMFERENCE * (1 - pct / 100)

  return (
    <Tooltip.Provider delayDuration={150}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <div
            className="flex cursor-default flex-col items-center gap-1.5 rounded-[var(--radius-inner)] border border-border-hairline bg-canvas/40 p-3 text-center transition-colors duration-150 hover:bg-surface-hover"
            role="group"
            aria-label={`${CATEGORY_LABEL[risk.category]}: ${SEVERITY_TAG_LABEL[risk.severity]} risk`}
          >
            <div className="relative h-16 w-16">
              <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90">
                <circle cx="32" cy="32" r={RADIUS} fill="none" stroke="var(--border-hairline)" strokeWidth="5" />
                <circle
                  cx="32"
                  cy="32"
                  r={RADIUS}
                  fill="none"
                  stroke={color}
                  strokeWidth="5"
                  strokeLinecap="round"
                  strokeDasharray={CIRCUMFERENCE}
                  strokeDashoffset={dashOffset}
                  className="transition-[stroke-dashoffset] duration-300 ease-out"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <Icon className="h-5 w-5 text-text-secondary" aria-hidden="true" />
              </div>
            </div>

            <span className="text-xs font-medium text-text-primary">{CATEGORY_LABEL[risk.category]}</span>
            <span
              className="text-mono-tag rounded px-1.5 py-0.5 normal-case tracking-normal"
              style={{ color, backgroundColor: `color-mix(in srgb, ${color} 14%, transparent)` }}
            >
              {SEVERITY_TAG_LABEL[risk.severity]}
            </span>
          </div>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side="top"
            sideOffset={6}
            className={cn(
              'card-hairline max-w-64 rounded-[var(--radius-inner)] bg-surface px-3 py-2 text-xs text-text-secondary',
              'z-50 select-none data-[state=delayed-open]:animate-in data-[state=delayed-open]:fade-in',
            )}
          >
            {risk.description}
            <Tooltip.Arrow className="fill-surface" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
