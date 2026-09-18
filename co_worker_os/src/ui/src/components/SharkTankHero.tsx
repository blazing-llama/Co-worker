import { AlertTriangle, CheckCircle2, TrendingDown } from 'lucide-react'
import { RiskGauge } from '@/components/RiskGauge'
import { cn } from '@/lib/utils'
import type { ConfidenceLevel, ProductRisk, Region, SharkTankVerdict } from '@/types'

interface SharkTankHeroProps {
  verdict: SharkTankVerdict
  region: Region
}

type VerdictStatus = 'viable' | 'pivot' | 'unviable'

const VERDICT_META: Record<
  VerdictStatus,
  { label: string; color: string; glow: string; icon: React.ComponentType<{ className?: string }> }
> = {
  viable: { label: 'Viable', color: 'var(--verdict-viable)', glow: 'var(--verdict-viable-glow)', icon: CheckCircle2 },
  pivot: { label: 'Pivot', color: 'var(--verdict-pivot)', glow: 'var(--verdict-pivot-glow)', icon: TrendingDown },
  unviable: { label: 'Unviable', color: 'var(--verdict-unviable)', glow: 'var(--verdict-unviable-glow)', icon: AlertTriangle },
}

/**
 * The backend's SharkTankVerdict has no single "Viable/Pivot/Unviable" field
 * (see src/core/schemas.py) -- only verdict_confidence and 4 risk severities.
 * This derives a display status from the risk severities: any risk marked
 * "high" is disqualifying-serious enough to warrant a second look (unviable
 * if 2+, pivot if 1); with zero high risks, low verdict_confidence still
 * reads as "pivot" rather than a false "viable". This is a presentational
 * heuristic over real backend data, not a value the model produced --
 * documented here and in docs/ImplementationPlan.md so it's never mistaken
 * for an agent's own verdict.
 */
function deriveVerdictStatus(risks: ProductRisk[], verdictConfidence: ConfidenceLevel): VerdictStatus {
  const highCount = risks.filter((r) => r.severity === 'high').length
  if (highCount >= 2) return 'unviable'
  if (highCount === 1) return 'pivot'
  if (verdictConfidence === 'low') return 'pivot'
  return 'viable'
}

function formatCurrency(usd: number, region: Region): string {
  if (region === 'india') {
    // TAM/SAM are stored in USD by the backend regardless of region; convert
    // to crores for an India-first display the way the design brief expects
    // ("₹4,200 Cr"), using a fixed illustrative rate -- flagged inline since
    // it's a display conversion, not a backend-sourced FX figure.
    const inr = usd * 83 // approx USD->INR, display purposes only
    const crores = inr / 1e7
    return `₹${crores.toLocaleString('en-IN', { maximumFractionDigits: 1 })} Cr`
  }
  if (usd >= 1e6) return `$${(usd / 1e6).toLocaleString('en-US', { maximumFractionDigits: 1 })}M`
  return `$${usd.toLocaleString('en-US')}`
}

const RISK_ORDER: ProductRisk['category'][] = ['value', 'usability', 'feasibility', 'viability']

export function SharkTankHero({ verdict, region }: SharkTankHeroProps) {
  const status = deriveVerdictStatus(verdict.risks, verdict.verdict_confidence)
  const meta = VERDICT_META[status]
  const StatusIcon = meta.icon
  const orderedRisks = RISK_ORDER.map((cat) => verdict.risks.find((r) => r.category === cat)).filter(
    (r): r is ProductRisk => r != null,
  )

  return (
    <div className="col-span-12 grid grid-cols-12 gap-5">
      {/* Cell 1: verdict banner */}
      <section className="card-hairline col-span-7 rounded-[var(--radius-outer)] bg-surface p-6">
        <div
          className="mb-5 flex items-center gap-2 rounded-[var(--radius-inner)] px-3 py-2"
          style={{ backgroundColor: meta.glow, color: meta.color }}
        >
          <StatusIcon className="h-4 w-4 shrink-0" />
          <span className="text-sm font-semibold">{meta.label}</span>
          <span className="text-mono-tag ml-auto normal-case tracking-normal opacity-80">
            confidence: {verdict.verdict_confidence}
          </span>
        </div>

        <div className="mb-5">
          <div className="text-mono-tag mb-1.5 text-text-muted">Unit Economics Summary</div>
          <p className="line-clamp-4 text-sm leading-relaxed text-text-secondary">{verdict.unit_economics_summary}</p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <MetricCard label="TAM / SAM" value={`${formatCurrency(verdict.tam_usd, region)} / ${formatCurrency(verdict.sam_usd, region)}`} />
          <MetricCard label="Defensibility / Moat" value={verdict.defensibility_notes} clamp />
        </div>
      </section>

      {/* Cell 2: 4-axis risk gauges */}
      <section className="card-hairline col-span-5 rounded-[var(--radius-outer)] bg-surface p-6">
        <h3 className="mb-4 text-sm font-semibold text-text-primary">Product Risk — 4 Axes</h3>
        <div className="grid grid-cols-2 gap-3">
          {orderedRisks.map((risk) => (
            <RiskGauge key={risk.category} risk={risk} />
          ))}
        </div>
      </section>
    </div>
  )
}

function MetricCard({ label, value, clamp = false }: { label: string; value: string; clamp?: boolean }) {
  return (
    <div className="rounded-[var(--radius-inner)] border border-border-hairline bg-canvas/40 p-3">
      <div className="text-mono-tag mb-1 text-text-muted">{label}</div>
      <div className={cn('font-display text-sm font-semibold text-text-primary', clamp && 'line-clamp-3 font-body font-normal')}>
        {value}
      </div>
    </div>
  )
}
