"""Product Manager agent: PRD generation, feature matrix, user flows.

Consumes ONLY ProductConstraints, never the user's raw prompt.
"""

from __future__ import annotations

from src.agents._common import append_feedback
from src.core.config import model_for
from src.core.ollama_client import ChatFn, default_chat_fn, parse_json_response
from src.core.schemas import PRDSpec, ProductConstraints

SYSTEM_PROMPT = """\
You are the Product Manager agent on a local AI startup team. Given a
ProductConstraints JSON object, return ONLY a JSON object matching the PRDSpec
schema: problem_statement, user_flows (list of {step_number, description}),
requirements (list of {id, description} where id matches "FR-XXX", zero-padded
3 digits, sequential starting at FR-001), mvp_features (non-empty list of
strings), and post_mvp_features (list of strings, may be empty). Every
requirement must be traceable to the given constraints and persona — never
invent scope the constraints don't support. Return raw JSON only, no prose, no
markdown fences.
"""


def run(constraints: ProductConstraints, chat_fn: ChatFn | None = None, feedback: str | None = None) -> PRDSpec:
    chat_fn = chat_fn or default_chat_fn(model_for("product_manager"))
    user_prompt = append_feedback(constraints.model_dump_json(), feedback)
    raw_output = chat_fn(SYSTEM_PROMPT, user_prompt)
    return parse_json_response(raw_output, PRDSpec)
