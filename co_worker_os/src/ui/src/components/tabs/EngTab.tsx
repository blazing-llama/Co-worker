import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { MonoIdTag } from '@/components/ui/tags'
import type { TechStackSpec } from '@/types'

const DEPT_COLOR = 'var(--dept-eng)'

const HTTP_METHOD_COLOR: Record<string, string> = {
  GET: 'var(--dept-gtm)',
  POST: 'var(--verdict-viable)',
  PUT: 'var(--verdict-pivot)',
  PATCH: 'var(--verdict-pivot)',
  DELETE: 'var(--verdict-unviable)',
}

interface EngTabProps {
  spec: TechStackSpec
}

/**
 * The design brief asked for an "Interactive System Architecture Diagram"
 * (Mermaid.js). src/core/schemas.py's TechStackSpec only gives
 * architecture_summary as free text, not a diagram schema -- rendering a
 * diagram would mean guessing structure the agent never specified, so this
 * shows the summary as text instead of fabricating a picture.
 */
export function EngTab({ spec }: EngTabProps) {
  return (
    <div className="grid grid-cols-12 gap-5">
      <section className="card-hairline col-span-12 rounded-[var(--radius-outer)] bg-surface p-5 lg:col-span-6">
        <h3 className="mb-3 text-sm font-semibold text-text-primary">Architecture Summary</h3>
        <p className="mb-5 text-sm leading-relaxed text-text-secondary">{spec.architecture_summary}</p>

        <h3 className="mb-3 text-sm font-semibold text-text-primary">Data Model</h3>
        <p className="text-sm leading-relaxed text-text-secondary">{spec.data_model_summary}</p>
      </section>

      <section className="card-hairline col-span-12 flex flex-col gap-5 rounded-[var(--radius-outer)] bg-surface p-5 lg:col-span-6">
        <div>
          <h3 className="mb-3 text-sm font-semibold text-text-primary">API Contracts</h3>
          <div className="space-y-1.5">
            {spec.api_contracts.map((contract) => (
              <ApiContractRow key={contract} contract={contract} />
            ))}
            {spec.api_contracts.length === 0 && <p className="text-sm text-text-muted">No API contracts returned.</p>}
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-sm font-semibold text-text-primary">TDD Test Suite (specs, not yet executed)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border-hairline text-text-muted">
                  <th className="pb-2 pr-3 font-medium">ID</th>
                  <th className="pb-2 pr-3 font-medium">Covers</th>
                  <th className="pb-2 font-medium">Description</th>
                </tr>
              </thead>
              <tbody>
                {spec.test_specs.map((test) => (
                  <tr key={test.id} className="border-b border-border-hairline/60 last:border-0">
                    <td className="py-2 pr-3 align-top">
                      <MonoIdTag id={test.id} accent={DEPT_COLOR} />
                    </td>
                    <td className="py-2 pr-3 align-top">
                      <MonoIdTag id={test.covers_requirement_id} accent="var(--dept-pm)" />
                    </td>
                    <td className="py-2 text-text-secondary">{test.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  )
}

function ApiContractRow({ contract }: { contract: string }) {
  const [copied, setCopied] = useState(false)
  const trimmed = contract.trim()
  const firstSpace = trimmed.indexOf(' ')
  const method = firstSpace === -1 ? '' : trimmed.slice(0, firstSpace).toUpperCase()
  const isKnownMethod = method in HTTP_METHOD_COLOR
  const methodColor = isKnownMethod ? HTTP_METHOD_COLOR[method] : 'var(--text-muted)'
  const path = isKnownMethod ? trimmed.slice(firstSpace + 1) : trimmed

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(contract)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard API unavailable (e.g. insecure context) -- fail silently, non-critical
    }
  }

  return (
    <div className="flex items-center gap-2 rounded-[var(--radius-inner)] border border-border-hairline bg-canvas/40 px-3 py-2">
      {isKnownMethod && (
        <span
          className="text-mono-tag inline-block w-14 shrink-0 rounded px-1.5 py-0.5 text-center normal-case"
          style={{ color: methodColor, backgroundColor: `color-mix(in srgb, ${methodColor} 14%, transparent)` }}
        >
          {method}
        </span>
      )}
      <span className="flex-1 truncate font-mono text-xs text-text-secondary">{path}</span>
      <button
        type="button"
        onClick={handleCopy}
        aria-label={`Copy ${contract}`}
        className="shrink-0 rounded p-1 text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
      >
        {copied ? <Check className="h-3.5 w-3.5 text-verdict-viable" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  )
}
