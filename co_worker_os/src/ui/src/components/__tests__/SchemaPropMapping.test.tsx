/**
 * Confirms each component maps its real Pydantic-schema-shaped prop (see
 * src/types.ts, mirroring src/core/schemas.py) onto the rendered DOM
 * correctly -- category-by-category, field-by-field -- not just "renders
 * without crashing."
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SharkTankHero } from '@/components/SharkTankHero'
import { PMTab } from '@/components/tabs/PMTab'
import { LegalTab } from '@/components/tabs/LegalTab'
import {
  legalFlagsFixtureNoWarning,
  legalFlagsFixtureWithWarning,
  prdSpecFixture,
  sharkTankVerdictFixture,
} from '@/test/fixtures'

describe('SharkTankVerdict -> SharkTankHero prop mapping', () => {
  it('maps each of the 4 risk categories to its own gauge with the correct severity', () => {
    render(<SharkTankHero verdict={sharkTankVerdictFixture} region="global" />)

    expect(screen.getByRole('group', { name: /value risk: high risk/i })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /usability risk: low risk/i })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /feasibility risk: high risk/i })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /viability risk: med risk/i })).toBeInTheDocument()
  })

  it('maps verdict_confidence into the confidence readout', () => {
    render(<SharkTankHero verdict={sharkTankVerdictFixture} region="global" />)
    expect(screen.getByText(/confidence: medium/i)).toBeInTheDocument()
  })

  it('maps unit_economics_summary and defensibility_notes verbatim', () => {
    render(<SharkTankHero verdict={sharkTankVerdictFixture} region="global" />)
    expect(screen.getByText(sharkTankVerdictFixture.unit_economics_summary)).toBeInTheDocument()
    expect(screen.getByText(sharkTankVerdictFixture.defensibility_notes)).toBeInTheDocument()
  })

  it('derives Unviable when 2+ risks are high severity (this fixture has exactly 2)', () => {
    render(<SharkTankHero verdict={sharkTankVerdictFixture} region="global" />)
    expect(screen.getByText('Unviable')).toBeInTheDocument()
  })

  it('derives Viable when no risk is high and confidence is not low', () => {
    const lowRiskVerdict = {
      ...sharkTankVerdictFixture,
      risks: sharkTankVerdictFixture.risks.map((r) => ({ ...r, severity: 'low' as const })),
      verdict_confidence: 'high' as const,
    }
    render(<SharkTankHero verdict={lowRiskVerdict} region="global" />)
    expect(screen.getByText('Viable')).toBeInTheDocument()
  })
})

describe('PRDSpec -> PMTab prop mapping', () => {
  it('maps problem_statement verbatim', () => {
    render(<PMTab spec={prdSpecFixture} />)
    expect(screen.getByText(prdSpecFixture.problem_statement)).toBeInTheDocument()
  })

  it('maps every FR-XXX requirement id and description', () => {
    render(<PMTab spec={prdSpecFixture} />)
    for (const req of prdSpecFixture.requirements) {
      expect(screen.getByText(req.id)).toBeInTheDocument()
      expect(screen.getByText(req.description)).toBeInTheDocument()
    }
  })

  it('maps user_flows in step_number order', () => {
    render(<PMTab spec={prdSpecFixture} />)
    const steps = screen.getAllByText(/^[12]$/)
    expect(steps.map((el) => el.textContent)).toEqual(['1', '2'])
  })

  it('maps mvp_features and post_mvp_features into separate lists', () => {
    render(<PMTab spec={prdSpecFixture} />)
    expect(screen.getByText('Address validation')).toBeInTheDocument()
    expect(screen.getByText('Subscription reorder')).toBeInTheDocument()
  })
})

describe('LegalFlags -> LegalTab prop mapping', () => {
  it('shows the CA/CS/Lawyer Required banner when ca_cs_lawyer_required is true', () => {
    render(<LegalTab flags={legalFlagsFixtureWithWarning} region="india" />)
    expect(screen.getByText('CA/CS/Lawyer Required')).toBeInTheDocument()
  })

  it('hides the banner when ca_cs_lawyer_required is false', () => {
    render(<LegalTab flags={legalFlagsFixtureNoWarning} region="india" />)
    expect(screen.queryByText('CA/CS/Lawyer Required')).not.toBeInTheDocument()
  })

  it('maps india_flags to the primary table when region is india', () => {
    render(<LegalTab flags={legalFlagsFixtureWithWarning} region="india" />)
    expect(screen.getByText('DPDP')).toBeInTheDocument()
    expect(screen.getByText(legalFlagsFixtureWithWarning.india_flags[0].description)).toBeInTheDocument()
  })

  it('swaps primary/secondary flag tables when region is global', () => {
    render(<LegalTab flags={legalFlagsFixtureWithWarning} region="global" />)
    expect(screen.getByRole('heading', { name: /^global \(gdpr/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /^india flags$/i })).toBeInTheDocument()
  })

  it('shows "No flags returned." for an empty flag list', () => {
    render(<LegalTab flags={legalFlagsFixtureWithWarning} region="india" />)
    // global_flags is empty in this fixture, so the secondary table is empty.
    expect(screen.getByText('No flags returned.')).toBeInTheDocument()
  })
})
