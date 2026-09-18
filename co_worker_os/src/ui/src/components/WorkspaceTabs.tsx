import * as Tabs from '@radix-ui/react-tabs'
import { Briefcase, Megaphone, Scale, Terminal } from 'lucide-react'
import { EngTab } from '@/components/tabs/EngTab'
import { GTMTab } from '@/components/tabs/GTMTab'
import { LegalTab } from '@/components/tabs/LegalTab'
import { PMTab } from '@/components/tabs/PMTab'
import { cn } from '@/lib/utils'
import type { GTMSentiment, LegalFlags, PRDSpec, Region, TechStackSpec } from '@/types'

interface WorkspaceTabsProps {
  pm: PRDSpec
  eng: TechStackSpec
  gtm: GTMSentiment
  legal: LegalFlags
  region: Region
}

const TABS = [
  { value: 'pm', label: 'PM Workspace', icon: Briefcase, color: 'var(--dept-pm)' },
  { value: 'eng', label: 'Engineering', icon: Terminal, color: 'var(--dept-eng)' },
  { value: 'gtm', label: 'GTM & Research', icon: Megaphone, color: 'var(--dept-gtm)' },
  { value: 'legal', label: 'Legal & Finance', icon: Scale, color: 'var(--dept-legal)' },
] as const

export function WorkspaceTabs({ pm, eng, gtm, legal, region }: WorkspaceTabsProps) {
  return (
    <Tabs.Root defaultValue="pm" className="col-span-12">
      <Tabs.List className="mb-4 flex gap-1 rounded-[var(--radius-inner)] border border-border-hairline bg-surface p-1">
        {TABS.map(({ value, label, icon: Icon, color }) => (
          <Tabs.Trigger
            key={value}
            value={value}
            className={cn(
              'group flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-text-secondary transition-colors duration-150',
              'hover:text-text-primary data-[state=active]:text-text-primary',
            )}
            style={{ '--tab-accent': color } as React.CSSProperties}
          >
            <span
              className="flex items-center gap-2 rounded-md px-2 py-1 transition-colors duration-150 group-data-[state=active]:bg-[color-mix(in_srgb,var(--tab-accent)_14%,transparent)]"
              style={{ color: 'inherit' }}
            >
              <Icon className="h-3.5 w-3.5 shrink-0 group-data-[state=active]:[color:var(--tab-accent)]" />
              {label}
            </span>
          </Tabs.Trigger>
        ))}
      </Tabs.List>

      <Tabs.Content value="pm" className="focus:outline-none">
        <PMTab spec={pm} />
      </Tabs.Content>
      <Tabs.Content value="eng" className="focus:outline-none">
        <EngTab spec={eng} />
      </Tabs.Content>
      <Tabs.Content value="gtm" className="focus:outline-none">
        <GTMTab sentiment={gtm} />
      </Tabs.Content>
      <Tabs.Content value="legal" className="focus:outline-none">
        <LegalTab flags={legal} region={region} />
      </Tabs.Content>
    </Tabs.Root>
  )
}
