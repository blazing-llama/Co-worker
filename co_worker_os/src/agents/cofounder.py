"""Co-Founder agent: Shark Tank lens — TAM/SAM, unit economics, defensibility,
and the 4 core product risks (value, usability, feasibility, viability).

Consumes ONLY ProductConstraints, never the user's raw prompt.
"""

from __future__ import annotations

from src.core.config import model_for
from src.core.ollama_client import ChatFn, default_chat_fn, parse_json_response
from src.core.schemas import ProductConstraints, SharkTankVerdict

SYSTEM_PROMPT = """\
You are the Co-Founder agent on a local AI startup team, evaluating ideas with a
Shark Tank investor's skepticism. Given a ProductConstraints JSON object, return
ONLY a JSON object matching the SharkTankVerdict schema: tam_usd, sam_usd,
unit_economics_summary, defensibility_notes, risks (exactly 4 entries, one each
for categories "value", "usability", "feasibility", "viability", each with a
severity of "high"/"medium"/"low"), and verdict_confidence ("high"/"medium"/"low").
Ground every number and claim in the given constraints — never invent market data
you cannot justify from what's provided. sam_usd must not exceed tam_usd.
Return raw JSON only, no prose, no markdown fences.
"""


def run(constraints: ProductConstraints, chat_fn: ChatFn | None = None) -> SharkTankVerdict:
    chat_fn = chat_fn or default_chat_fn(model_for("cofounder"))
    user_prompt = constraints.model_dump_json()
    raw_output = chat_fn(SYSTEM_PROMPT, user_prompt)
    return parse_json_response(raw_output, SharkTankVerdict)
