import { useRef } from 'react'
import { Loader2, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'

const CATEGORIES = ['Digital', 'Physical/Food', 'D2C', 'B2B SaaS'] as const
export type Category = (typeof CATEGORIES)[number]

interface InputConsoleProps {
  value: string
  onChange: (value: string) => void
  category: Category | null
  onCategoryChange: (category: Category | null) => void
  onRun: () => void
  isRunning: boolean
  runStep: string | null
}

/** Zone 2: Action Engine. A borderless auto-expanding textarea reads as an
 * input surface, not a form field -- the card wrapper carries the visual
 * weight instead, per the brief's "clean placeholder, no chrome" note. */
export function InputConsole({
  value,
  onChange,
  category,
  onCategoryChange,
  onRun,
  isRunning,
  runStep,
}: InputConsoleProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      if (value.trim() && !isRunning) onRun()
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    onChange(e.target.value)
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${el.scrollHeight}px`
    }
  }

  return (
    <section className="card-hairline col-span-12 rounded-[var(--radius-outer)] bg-surface p-5">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder="Describe your business idea, feature, or strategic problem…"
        rows={3}
        className="min-h-[100px] w-full resize-none border-0 bg-transparent text-base leading-relaxed text-text-primary placeholder:text-text-muted focus:outline-none"
      />

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border-hairline pt-4">
        <div className="flex flex-wrap items-center gap-2">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => onCategoryChange(category === c ? null : c)}
              className={cn(
                'text-mono-tag rounded-[var(--radius-inner)] border px-2.5 py-1.5 normal-case tracking-normal transition-colors duration-150',
                category === c
                  ? 'border-dept-pm bg-dept-pm/10 text-dept-pm'
                  : 'border-border-hairline text-text-secondary hover:text-text-primary',
              )}
            >
              {c}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={onRun}
          disabled={!value.trim() || isRunning}
          className={cn(
            'flex items-center gap-2 rounded-[var(--radius-inner)] bg-dept-pm px-4 py-2 text-sm font-semibold text-white transition-all duration-150',
            'shadow-[0_0_24px_-4px_rgba(99,102,241,0.5)] hover:scale-[1.02] active:scale-[0.98]',
            'disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:hover:scale-100',
          )}
        >
          {isRunning ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{runStep ?? 'Running…'}</span>
            </>
          ) : (
            <>
              <Zap className="h-4 w-4" />
              <span>Run Co-Worker Team</span>
            </>
          )}
        </button>
      </div>
    </section>
  )
}
