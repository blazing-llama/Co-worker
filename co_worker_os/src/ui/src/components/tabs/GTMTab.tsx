import { ExternalLink, TrendingUp } from 'lucide-react'
import { ConfidenceTag } from '@/components/ui/tags'
import type { GTMSentiment } from '@/types'

const DEPT_COLOR = 'var(--dept-gtm)'

interface GTMTabProps {
  sentiment: GTMSentiment
}

/**
 * The design brief asked for a "sentiment breakdown meter" and CAC estimates.
 * src/core/schemas.py's GTMSentiment has neither a numeric sentiment score
 * nor a CAC field -- only per-theme confidence tags and free-text channel
 * strategy -- so this shows the real grounded themes (with their source link,
 * per the agent's grounding requirement) rather than inventing a percentage.
 */
export function GTMTab({ sentiment }: GTMTabProps) {
  return (
    <div className="grid grid-cols-12 gap-5">
      <section className="card-hairline col-span-12 rounded-[var(--radius-outer)] bg-surface p-5 lg:col-span-7">
        <h3 className="mb-3 text-sm font-semibold text-text-primary">Scraped Market Sentiment</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {sentiment.customer_feedback_themes.map((theme, i) => (
            <div key={i} className="rounded-[var(--radius-inner)] border border-border-hairline bg-canvas/40 p-3">
              <div className="mb-1.5 flex items-start justify-between gap-2">
                <span className="text-sm font-medium text-text-primary">{theme.theme}</span>
                <ConfidenceTag level={theme.confidence} />
              </div>
              <p className="mb-2 line-clamp-3 text-xs text-text-secondary">{theme.supporting_quote_or_stat}</p>
              <a
                href={theme.source_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-dept-gtm hover:underline"
              >
                Source <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          ))}
          {sentiment.customer_feedback_themes.length === 0 && (
            <p className="text-sm text-text-muted sm:col-span-2">No scraped feedback themes returned.</p>
          )}
        </div>

        <h3 className="mt-5 mb-3 text-sm font-semibold text-text-primary">Market Trends</h3>
        <div className="flex flex-wrap gap-2">
          {sentiment.market_trends.map((trend, i) => (
            <span
              key={i}
              className="text-mono-tag inline-flex items-center gap-1 rounded-[var(--radius-inner)] border px-2 py-1 normal-case tracking-normal"
              style={{ borderColor: 'color-mix(in srgb, var(--dept-gtm) 35%, transparent)', color: DEPT_COLOR }}
            >
              <TrendingUp className="h-3 w-3" />
              {trend}
            </span>
          ))}
          {sentiment.market_trends.length === 0 && <p className="text-sm text-text-muted">No market trends returned.</p>}
        </div>
      </section>

      <section className="col-span-12 flex flex-col gap-5 lg:col-span-5">
        <div className="card-hairline rounded-[var(--radius-outer)] bg-surface p-5">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Competitor Price Benchmarking</h3>
          <table className="w-full text-left text-sm">
            <tbody>
              {Object.entries(sentiment.pricing_benchmarks_usd).map(([name, price]) => (
                <tr key={name} className="border-b border-border-hairline/60 last:border-0">
                  <td className="py-2 text-text-secondary">{name}</td>
                  <td className="py-2 text-right font-mono text-text-primary">${price.toLocaleString()}</td>
                </tr>
              ))}
              {Object.keys(sentiment.pricing_benchmarks_usd).length === 0 && (
                <tr>
                  <td className="py-2 text-sm text-text-muted">No pricing benchmarks returned.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="card-hairline rounded-[var(--radius-outer)] bg-surface p-5">
          <h3 className="mb-2 text-sm font-semibold text-text-primary">Acquisition Channel Strategy</h3>
          <p className="text-sm leading-relaxed text-text-secondary">{sentiment.channel_strategy}</p>
        </div>
      </section>
    </div>
  )
}
