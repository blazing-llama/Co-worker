import { AlertTriangle, ScaleIcon, ShieldAlert } from 'lucide-react'
import { ConfidenceTag } from '@/components/ui/tags'
import type { LegalFlag, LegalFlags, Region } from '@/types'

interface LegalTabProps {
  flags: LegalFlags
  region: Region
}

/**
 * See docs/Legal_Finance_Boundaries.md: this agent flags risk categories,
 * it never asserts compliance or drafts usable legal text -- the UI mirrors
 * that boundary by only ever rendering flags and the ca_cs_lawyer_required
 * signal, never a "compliant" claim.
 */
export function LegalTab({ flags, region }: LegalTabProps) {
  const primaryFlags = region === 'india' ? flags.india_flags : flags.global_flags
  const secondaryFlags = region === 'india' ? flags.global_flags : flags.india_flags
  const primaryLabel = region === 'india' ? 'India (DPDP Act 2023 / IT Act 2000 / GST)' : 'Global (GDPR / CCPA / other)'
  const secondaryLabel = region === 'india' ? 'Global' : 'India'

  return (
    <div className="grid grid-cols-12 gap-5">
      {flags.ca_cs_lawyer_required && (
        <div
          className="col-span-12 flex items-start gap-3 rounded-[var(--radius-outer)] border p-4"
          style={{
            borderColor: 'color-mix(in srgb, var(--dept-legal-warning) 40%, transparent)',
            backgroundColor: 'color-mix(in srgb, var(--dept-legal-warning) 10%, transparent)',
          }}
        >
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" style={{ color: 'var(--dept-legal-warning)' }} />
          <div>
            <div className="font-semibold" style={{ color: 'var(--dept-legal-warning)' }}>
              CA/CS/Lawyer Required
            </div>
            <p className="mt-1 text-sm text-text-secondary">
              At least one flag below crosses from informational into filing, contract, or regulatory judgment
              territory. This is a routing signal, not legal advice — consult a licensed professional before acting.
            </p>
          </div>
        </div>
      )}

      <section className="card-hairline col-span-7 rounded-[var(--radius-outer)] bg-surface p-5">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
          <ScaleIcon className="h-4 w-4 shrink-0" style={{ color: 'var(--dept-legal)' }} />
          {primaryLabel} Flags
        </h3>
        <FlagTable flagList={primaryFlags} />
      </section>

      <section className="card-hairline col-span-5 rounded-[var(--radius-outer)] bg-surface p-5">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
          <ShieldAlert className="h-4 w-4 shrink-0 text-text-muted" />
          {secondaryLabel} Flags
        </h3>
        <FlagTable flagList={secondaryFlags} muted />
      </section>
    </div>
  )
}

function FlagTable({ flagList, muted = false }: { flagList: LegalFlag[]; muted?: boolean }) {
  if (flagList.length === 0) {
    return <p className="text-sm text-text-muted">No flags returned.</p>
  }
  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b border-border-hairline text-text-muted">
          <th className="pb-2 pr-3 font-medium">Category</th>
          <th className="pb-2 pr-3 font-medium">Description</th>
          <th className="pb-2 font-medium">Confidence</th>
        </tr>
      </thead>
      <tbody>
        {flagList.map((flag, i) => (
          <tr key={i} className="border-b border-border-hairline/60 last:border-0">
            <td className="py-2 pr-3 align-top">
              <span
                className="text-mono-tag inline-block rounded border px-1.5 py-0.5 normal-case"
                style={{
                  borderColor: muted ? 'var(--border-hairline)' : 'color-mix(in srgb, var(--dept-legal) 40%, transparent)',
                  color: muted ? 'var(--text-muted)' : 'var(--dept-legal)',
                }}
              >
                {flag.category}
              </span>
            </td>
            <td className="py-2 pr-3 align-top text-text-secondary">{flag.description}</td>
            <td className="py-2 align-top">
              <ConfidenceTag level={flag.confidence} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
