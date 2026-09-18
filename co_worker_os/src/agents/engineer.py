"""Engineering Lead agent: architecture, API contracts, TDD test specs.

Consumes ONLY ProductConstraints, never the user's raw prompt.
"""

from __future__ import annotations

from src.core.config import model_for
from src.core.ollama_client import ChatFn, default_chat_fn, parse_json_response
from src.core.schemas import ProductConstraints, TechStackSpec

SYSTEM_PROMPT = """\
You are the Engineering Lead agent on a local AI startup team. Given a
ProductConstraints JSON object, return ONLY a JSON object matching the
TechStackSpec schema: architecture_summary, data_model_summary, api_contracts
(list of strings, e.g. "POST /idea"), and test_specs (non-empty list of
{id, description, covers_requirement_id} where id matches "TEST-XXX" and
covers_requirement_id matches "FR-XXX"). Follow TDD RED-GREEN discipline: every
test_spec must be written as if it will fail before the corresponding
implementation exists. Respect tech_constraints from the input exactly — never
propose a stack element that violates a stated constraint (e.g. "must run
offline"). Return raw JSON only, no prose, no markdown fences.
"""


def run(constraints: ProductConstraints, chat_fn: ChatFn | None = None) -> TechStackSpec:
    chat_fn = chat_fn or default_chat_fn(model_for("engineer"))
    user_prompt = constraints.model_dump_json()
    raw_output = chat_fn(SYSTEM_PROMPT, user_prompt)
    return parse_json_response(raw_output, TechStackSpec)
