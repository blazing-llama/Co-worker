"""Legal/Finance Strategy agent: India DPDP Act 2023 / IT Act / GST scanning +
mandatory ca_cs_lawyer_required flagging.

Consumes ONLY ProductConstraints, never the user's raw prompt. Scope is bounded
by docs/Legal_Finance_Boundaries.md — this agent flags risk categories, it never
asserts compliance or drafts usable legal text.
"""

from __future__ import annotations

from src.core.config import model_for
from src.core.ollama_client import ChatFn, default_chat_fn, parse_json_response
from src.core.schemas import LegalFlags, ProductConstraints, Region

SYSTEM_PROMPT = """\
You are the Legal/Finance Strategy agent on a local AI startup team. Given a
ProductConstraints JSON object, return ONLY a JSON object matching the
LegalFlags schema: india_flags (list of {category, description, confidence}),
global_flags (same shape), and ca_cs_lawyer_required (boolean).

Scope boundary (see docs/Legal_Finance_Boundaries.md) — you MUST:
- Flag likely India DPDP Act 2023, GST, and IT Act 2000 applicability based on
  described data handling and revenue model, when region is "india".
- Flag analogous global categories (GDPR, CCPA) only when region is "global".
- Set ca_cs_lawyer_required=true whenever a flag requires filing, a contract, or
  regulatory judgment, not just information.
- Default confidence to "medium" on any regulatory claim unless directly
  grounded in the constraints text.
- Never assert compliance ("this is DPDP-compliant") — only flag risk categories.
- Never generate a usable contract, ToS, or exact tax figure — flags only.

Return raw JSON only, no prose, no markdown fences.
"""


def run(constraints: ProductConstraints, chat_fn: ChatFn | None = None) -> LegalFlags:
    chat_fn = chat_fn or default_chat_fn(model_for("legal_finance"))
    system_prompt = SYSTEM_PROMPT
    if constraints.region == Region.INDIA:
        system_prompt += "\nThis product's region is India — prioritize DPDP, GST, and IT Act flags.\n"
    user_prompt = constraints.model_dump_json()
    raw_output = chat_fn(system_prompt, user_prompt)
    return parse_json_response(raw_output, LegalFlags)
