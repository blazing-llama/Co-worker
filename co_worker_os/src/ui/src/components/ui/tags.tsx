import { cn } from '@/lib/utils'
import type { ConfidenceLevel } from '@/types'

const CONFIDENCE_COLOR: Record<ConfidenceLevel, string> = {
  high: 'var(--verdict-viable)',
  medium: 'var(--verdict-pivot)',
  low: 'var(--verdict-unviable)',
}

/** A confidence/severity chip, colored consistently with the risk gauges
 * (Zone 3) so the same visual language reads the same meaning everywhere. */
export function ConfidenceTag({ level }: { level: ConfidenceLevel }) {
  const color = CONFIDENCE_COLOR[level]
  return (
    <span
      className="text-mono-tag inline-block shrink-0 rounded px-1.5 py-0.5 normal-case tracking-normal"
      style={{ color, backgroundColor: `color-mix(in srgb, ${color} 14%, transparent)` }}
    >
      {level}
    </span>
  )
}

/** JetBrains Mono uppercase chip for FR-XXX / TEST-XXX IDs, per the design
 * brief's "Code, Schema Dumps & Metadata Tags" typography rule. */
export function MonoIdTag({ id, accent }: { id: string; accent?: string }) {
  return (
    <span
      className={cn('text-mono-tag inline-block shrink-0 rounded border px-1.5 py-0.5 normal-case')}
      style={{
        borderColor: accent ? `color-mix(in srgb, ${accent} 40%, transparent)` : undefined,
        color: accent,
      }}
    >
      {id}
    </span>
  )
}
