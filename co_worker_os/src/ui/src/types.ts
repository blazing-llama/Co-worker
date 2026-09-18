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
