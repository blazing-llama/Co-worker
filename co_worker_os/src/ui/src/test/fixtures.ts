/**
 * Shared test fixtures mirroring src/core/schemas.py's real Pydantic
 * contracts (via src/types.ts). Kept in one place so every component test
 * exercises the same shape the backend actually returns, rather than each
 * test inventing its own ad hoc object.
 */

import type { GTMSentiment, LegalFlags, PRDSpec, SharkTankVerdict, TechStackSpec } from '@/types'

export const sharkTankVerdictFixture: SharkTankVerdict = {
  tam_usd: 850_000_000,
  sam_usd: 45_000_000,
  unit_economics_summary: 'Average order value ~450, 22% contribution margin.',
  defensibility_notes: 'Weak near-term moat; competitors can replicate quickly.',
  risks: [
    { category: 'value', description: 'Unclear willingness to pay a premium.', severity: 'high' },
    { category: 'usability', description: 'Familiar UPI-based checkout flow.', severity: 'low' },
    { category: 'feasibility', description: 'Cold-chain logistics harder outside metros.', severity: 'high' },
    { category: 'viability', description: 'Well-funded competitors already active.', severity: 'medium' },
  ],
  verdict_confidence: 'medium',
}

export const prdSpecFixture: PRDSpec = {
  problem_statement: 'Tier-2 city residents lack reliable same-day delivery.',
  user_flows: [
    { step_number: 1, description: 'User sets delivery location' },
    { step_number: 2, description: 'User browses catalog' },
  ],
  requirements: [
    { id: 'FR-001', description: 'Accept and validate delivery address' },
    { id: 'FR-002', description: 'Display real-time inventory' },
  ],
  mvp_features: ['Address validation', 'Catalog browsing'],
  post_mvp_features: ['Subscription reorder'],
}

export const techStackSpecFixture: TechStackSpec = {
  architecture_summary: 'FastAPI backend with Postgres and Redis.',
  data_model_summary: 'Core entities: User, Store, Product, Order.',
  api_contracts: ['POST /orders', 'GET /stores/{id}/catalog'],
  test_specs: [{ id: 'TEST-001', description: 'Rejects out-of-radius addresses', covers_requirement_id: 'FR-001' }],
}

export const gtmSentimentFixture: GTMSentiment = {
  customer_feedback_themes: [
    {
      theme: 'Price sensitivity over speed',
      supporting_quote_or_stat: "I'd rather wait an hour and save money.",
      source_url: 'https://reddit.com/r/example',
      confidence: 'medium',
    },
  ],
  market_trends: ['Rising smartphone penetration'],
  pricing_benchmarks_usd: { 'Competitor A': 4.99 },
  channel_strategy: 'WhatsApp-first community marketing.',
}

export const legalFlagsFixtureWithWarning: LegalFlags = {
  india_flags: [
    { category: 'DPDP', description: 'Collects delivery address and payment data.', confidence: 'medium' },
    { category: 'GST', description: 'Marketplace facilitator model likely triggers GST.', confidence: 'medium' },
  ],
  global_flags: [],
  ca_cs_lawyer_required: true,
}

export const legalFlagsFixtureNoWarning: LegalFlags = {
  india_flags: [],
  global_flags: [],
  ca_cs_lawyer_required: false,
}
