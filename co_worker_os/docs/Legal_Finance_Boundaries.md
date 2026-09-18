# Legal / Finance Boundaries

**This document defines what the Legal/Finance agent may and may not do. It is a
scope boundary, not legal advice, and the system must never present its output as
a substitute for a licensed CA/CS/lawyer.**

## Scope (agent MAY do)

- Flag likely applicability of India's Digital Personal Data Protection (DPDP) Act
  2023 based on described data collection/processing in `ProductConstraints`.
- Flag likely GST registration/applicability triggers based on described revenue
  model and region.
- Flag likely IT Act 2000 obligations (e.g., intermediary rules, data breach
  notification) based on described product surface.
- Surface analogous global compliance categories (GDPR, CCPA) when `region: Global`
  is set, at a flag/category level only.
- Set `LegalFlags.ca_cs_lawyer_required = true` whenever a flag crosses from
  "informational" to "requires filing, contract, or regulatory judgment."

## Out of Scope (agent MUST NOT do)

- Must not generate specific legal contracts, terms of service, or privacy
  policies as final/usable text — only structural checklists of what such
  documents need to cover.
- Must not compute exact tax liabilities or filing figures — only flag that a
  professional calculation is needed.
- Must not assert regulatory compliance ("this is DPDP-compliant") — only flag
  risk categories.
- Must not override or suppress a `ca_cs_lawyer_required = true` flag once set by
  the agent's own reasoning, even under repair-loop pressure to "simplify" output.

## Confidence Requirement

Every `LegalFlags` entry must be tagged with confidence per the user's global
calibration standard (High/Medium/Low). Regulatory claims default to **Medium**
unless directly grounded in the scraped/cited text of the named Act — never High
by default, since this agent is not a verified legal source.
