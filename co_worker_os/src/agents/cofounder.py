"""Co-Founder agent: Shark Tank lens — TAM/SAM, unit economics, defensibility,
and the 4 core product risks (value, usability, feasibility, viability).

Consumes ONLY ProductConstraints, never the user's raw prompt.
"""

from __future__ import annotations

from src.agents._common import append_feedback
from src.core.config import model_for
from src.core.ollama_client import ChatFn, default_chat_fn, parse_json_response
from src.core.schemas import ProductConstraints, SharkTankVerdict

SYSTEM_PROMPT = """\
You are the Co-Founder agent on a local AI startup team, evaluating ideas with a
Shark Tank investor's skepticism. Given a ProductConstraints JSON object, return
ONLY a JSON object matching the SharkTankVerdict schema: tam_usd, sam_usd,
unit_economics_summary, defensibility_notes, risks, and verdict_confidence
("high"/"medium"/"low").

unit_economics_summary MUST show real arithmetic, not vague description. If
the idea_summary or tech_constraints give ANY concrete numbers (a cost, a
price, a production rate, a quantity, a time period), you MUST use those exact
numbers to compute at least one of: cost per unit, revenue per unit/hour/day,
gross margin, or payback period -- state the calculation inline (e.g. "machine
costs 65,000; at 1,300 units/hour it pays back in X hours of production at Y
margin per unit"). Only write "insufficient data to compute unit economics"
if the constraints truly give no usable numbers at all -- never replace a
calculation with generic filler sentences.

Never output a raw field name (like "machine_cost" or "tech_constraints") as a
word in your prose -- always translate it into a real English phrase (e.g.
"the machine's cost" not "machine_cost").

"risks" MUST be a JSON array of EXACTLY 4 objects, no more and no fewer. Each
object has "category", "description", "severity" ("high"/"medium"/"low"). The
4 "category" values must be EXACTLY these 4 strings, lowercase, one each,
nothing else: "value", "usability", "feasibility", "viability".

Ground every number and claim in the given constraints — never invent market data
you cannot justify from what's provided. sam_usd must not exceed tam_usd.
Return raw JSON only, no prose, no markdown fences.
"""


def run(constraints: ProductConstraints, chat_fn: ChatFn | None = None, feedback: str | None = None) -> SharkTankVerdict:
    chat_fn = chat_fn or default_chat_fn(model_for("cofounder"))
    user_prompt = append_feedback(constraints.model_dump_json(), feedback)
    raw_output = chat_fn(SYSTEM_PROMPT, user_prompt)
    return parse_json_response(raw_output, SharkTankVerdict)
