import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { WorkspaceTabs } from '@/components/WorkspaceTabs'
import {
  gtmSentimentFixture,
  legalFlagsFixtureWithWarning,
  prdSpecFixture,
  techStackSpecFixture,
} from '@/test/fixtures'

/**
 * "5 co-worker roles" per the product brief means Co-Founder, PM, Engineer,
 * GTM, Legal -- but Co-Founder renders in the Shark Tank hero (Zone 3), not
 * as a WorkspaceTabs tab (see docs/Architecture.md's zone layout). This
 * suite covers the 4 tabs that actually exist in WorkspaceTabs; Co-Founder
 * rendering is covered separately in SchemaPropMapping.test.tsx.
 */
function renderTabs() {
  return render(
    <WorkspaceTabs
      pm={prdSpecFixture}
      eng={techStackSpecFixture}
      gtm={gtmSentimentFixture}
      legal={legalFlagsFixtureWithWarning}
      region="india"
    />,
  )
}

describe('WorkspaceTabs switching', () => {
  it('renders all 4 departmental tab triggers', () => {
    renderTabs()
    expect(screen.getByRole('tab', { name: /pm workspace/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /engineering/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /gtm & research/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /legal & finance/i })).toBeInTheDocument()
  })

  it('shows the PM tab content by default', () => {
    renderTabs()
    expect(screen.getByText('Problem Statement')).toBeInTheDocument()
  })

  it('switches to Engineering content on click', async () => {
    const user = userEvent.setup()
    renderTabs()
    await user.click(screen.getByRole('tab', { name: /engineering/i }))
    expect(screen.getByText('Architecture Summary')).toBeInTheDocument()
    expect(screen.queryByText('Problem Statement')).not.toBeInTheDocument()
  })

  it('switches to GTM & Research content on click', async () => {
    const user = userEvent.setup()
    renderTabs()
    await user.click(screen.getByRole('tab', { name: /gtm & research/i }))
    expect(screen.getByText('Scraped Market Sentiment')).toBeInTheDocument()
  })

  it('switches to Legal & Finance content on click, including the warning banner', async () => {
    const user = userEvent.setup()
    renderTabs()
    await user.click(screen.getByRole('tab', { name: /legal & finance/i }))
    expect(screen.getByText('CA/CS/Lawyer Required')).toBeInTheDocument()
  })

  it('switches back to PM content after visiting another tab', async () => {
    const user = userEvent.setup()
    renderTabs()
    await user.click(screen.getByRole('tab', { name: /engineering/i }))
    await user.click(screen.getByRole('tab', { name: /pm workspace/i }))
    expect(screen.getByText('Problem Statement')).toBeInTheDocument()
  })

  it('marks only the active tab as selected', async () => {
    const user = userEvent.setup()
    renderTabs()
    await user.click(screen.getByRole('tab', { name: /gtm & research/i }))
    expect(screen.getByRole('tab', { name: /gtm & research/i })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: /pm workspace/i })).toHaveAttribute('aria-selected', 'false')
  })
})
