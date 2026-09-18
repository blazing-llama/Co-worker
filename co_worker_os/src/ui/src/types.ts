/**
 * TypeScript mirrors of src/core/schemas.py's Pydantic contracts, as they
 * actually appear on the wire from POST /api/run-team (via
 * RunTeamResponse.model_dump(mode="json")). Keep these in sync with
 * schemas.py by hand -- there's no shared codegen yet.
 */

export type ConfidenceLevel = 'high' | 'medium' | 'low'
export type Region = 'india' | 'global'

export interface ProductConstraints {
  idea_summary: string
  target_persona: string
  budget_usd: number
  timeline_weeks: number
  tech_constraints: string[]
  region: Region
}

export type RiskCategory = 'value' | 'usability' | 'feasibility' | 'viability'

export interface ProductRisk {
  category: RiskCategory
  description: string
  severity: ConfidenceLevel
}

export interface SharkTankVerdict {
  tam_usd: number
  sam_usd: number
  unit_economics_summary: string
  defensibility_notes: string
  risks: ProductRisk[]
  verdict_confidence: ConfidenceLevel
}

// --- Product Manager ---

export interface UserFlowStep {
  step_number: number
  description: string
}

export interface FunctionalRequirement {
  id: string // "FR-XXX"
  description: string
}

export interface PRDSpec {
  problem_statement: string
  user_flows: UserFlowStep[]
  requirements: FunctionalRequirement[]
  mvp_features: string[]
  post_mvp_features: string[]
}

// --- Engineering ---

export interface TestSpec {
  id: string // "TEST-XXX"
  description: string
  covers_requirement_id: string // "FR-XXX"
}

export interface TechStackSpec {
  architecture_summary: string
  data_model_summary: string
  api_contracts: string[]
  test_specs: TestSpec[]
}

// --- GTM & Research ---

export interface MarketTheme {
  theme: string
  supporting_quote_or_stat: string
  source_url: string
  confidence: ConfidenceLevel
}

export interface GTMSentiment {
  customer_feedback_themes: MarketTheme[]
  market_trends: string[]
  pricing_benchmarks_usd: Record<string, number>
  channel_strategy: string
}

// --- Legal & Finance ---

export interface LegalFlag {
  category: string
  description: string
  confidence: ConfidenceLevel
}

export interface LegalFlags {
  india_flags: LegalFlag[]
  global_flags: LegalFlag[]
  ca_cs_lawyer_required: boolean
}
