/**
 * Placeholder shown between "Run" being clicked and the first agent output
 * landing, so the Bento area isn't blank while the stream connects. No
 * skeleton/loading placeholder existed anywhere in the app before this --
 * added alongside the regression test suite that exercises it.
 */
export function RunSkeleton() {
  return (
    <div className="col-span-12 grid grid-cols-12 gap-5" data-testid="run-skeleton" role="status" aria-label="Running the Co-Worker team">
      <div className="card-hairline col-span-7 animate-pulse space-y-3 rounded-[var(--radius-outer)] bg-surface p-6">
        <div className="h-8 w-32 rounded-[var(--radius-inner)] bg-surface-hover" />
        <div className="h-4 w-full rounded bg-surface-hover" />
        <div className="h-4 w-2/3 rounded bg-surface-hover" />
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="h-16 rounded-[var(--radius-inner)] bg-surface-hover" />
          <div className="h-16 rounded-[var(--radius-inner)] bg-surface-hover" />
        </div>
      </div>
      <div className="card-hairline col-span-5 animate-pulse rounded-[var(--radius-outer)] bg-surface p-6">
        <div className="mb-4 h-4 w-40 rounded bg-surface-hover" />
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 rounded-[var(--radius-inner)] bg-surface-hover" />
          ))}
        </div>
      </div>
    </div>
  )
}
