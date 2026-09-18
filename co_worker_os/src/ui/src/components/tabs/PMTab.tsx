import { CheckCircle2, Circle } from 'lucide-react'
import { MonoIdTag } from '@/components/ui/tags'
import type { PRDSpec } from '@/types'

const DEPT_COLOR = 'var(--dept-pm)'

interface PMTabProps {
  spec: PRDSpec
}

/**
 * The design brief asked for "interactive persona cards with pain points" on
 * the left. src/core/schemas.py's PRDSpec has no persona field at all -- only
 * problem_statement and user_flows -- so this shows those instead of
 * fabricating personas the agent never produced.
 */
export function PMTab({ spec }: PMTabProps) {
  return (
    <div className="grid grid-cols-12 gap-5">
      <section className="card-hairline col-span-5 rounded-[var(--radius-outer)] bg-surface p-5">
        <h3 className="mb-3 text-sm font-semibold text-text-primary">Problem Statement</h3>
        <p className="mb-5 text-sm leading-relaxed text-text-secondary">{spec.problem_statement}</p>

        <h3 className="mb-3 text-sm font-semibold text-text-primary">User Flow</h3>
        <ol className="space-y-2">
          {spec.user_flows.map((step) => (
            <li key={step.step_number} className="flex gap-3 text-sm">
              <span
                className="text-mono-tag flex h-5 w-5 shrink-0 items-center justify-center rounded-full normal-case"
                style={{ backgroundColor: 'color-mix(in srgb, var(--dept-pm) 16%, transparent)', color: DEPT_COLOR }}
              >
                {step.step_number}
              </span>
              <span className="text-text-secondary">{step.description}</span>
            </li>
          ))}
          {spec.user_flows.length === 0 && <li className="text-sm text-text-muted">No user flow steps returned.</li>}
        </ol>
      </section>

      <section className="card-hairline col-span-7 rounded-[var(--radius-outer)] bg-surface p-5">
        <h3 className="mb-3 text-sm font-semibold text-text-primary">MVP Feature Backlog</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-hairline text-text-muted">
                <th className="pb-2 pr-3 font-medium">ID</th>
                <th className="pb-2 font-medium">Requirement</th>
              </tr>
            </thead>
            <tbody>
              {spec.requirements.map((req) => (
                <tr key={req.id} className="border-b border-border-hairline/60 last:border-0">
                  <td className="py-2 pr-3 align-top">
                    <MonoIdTag id={req.id} accent={DEPT_COLOR} />
                  </td>
                  <td className="py-2 text-text-secondary">{req.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-4">
          <FeatureList title="MVP" icon={CheckCircle2} items={spec.mvp_features} color={DEPT_COLOR} />
          <FeatureList title="Post-MVP" icon={Circle} items={spec.post_mvp_features} color="var(--text-muted)" muted />
        </div>
      </section>
    </div>
  )
}

function FeatureList({
  title,
  icon: Icon,
  items,
  color,
  muted = false,
}: {
  title: string
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>
  items: string[]
  color: string
  muted?: boolean
}) {
  return (
    <div>
      <div className="text-mono-tag mb-2 text-text-muted">{title}</div>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item} className={`flex items-start gap-2 text-sm ${muted ? 'text-text-muted' : 'text-text-secondary'}`}>
            <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color }} />
            <span>{item}</span>
          </li>
        ))}
        {items.length === 0 && <li className="text-sm text-text-muted">None returned.</li>}
      </ul>
    </div>
  )
}
