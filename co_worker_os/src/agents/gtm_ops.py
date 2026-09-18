"""GTM/Research Lead agent: channel strategy, positioning, scraped-sentiment
grounding.

Consumes ONLY ProductConstraints (plus optional pre-scraped markdown context
from src/scrapers/) — never the user's raw prompt, and never invents market
claims it cannot trace to that scraped context.
"""

from __future__ import annotations

from src.agents._common import append_feedback
from src.core.config import model_for
from src.core.ollama_client import ChatFn, default_chat_fn, parse_json_response
from src.core.schemas import GTMSentiment, ProductConstraints

SYSTEM_PROMPT = """\
You are the GTM & Research Lead agent on a local AI startup team. Given a
ProductConstraints JSON object (and, when provided, scraped market/social/video
research as markdown), return ONLY a JSON object matching the GTMSentiment
schema: customer_feedback_themes (list of {theme, supporting_quote_or_stat,
source_url, confidence}), market_trends (list of strings), pricing_benchmarks_usd
(dict of competitor/benchmark name to price), and channel_strategy. Every
customer_feedback_themes entry's supporting_quote_or_stat and source_url MUST be
drawn from the provided scraped context — if no scraped context is provided,
return an empty customer_feedback_themes list rather than inventing one. Return
raw JSON only, no prose, no markdown fences.
"""


def run(
    constraints: ProductConstraints,
    chat_fn: ChatFn | None = None,
    scraped_context: str | None = None,
    feedback: str | None = None,
) -> GTMSentiment:
    chat_fn = chat_fn or default_chat_fn(model_for("gtm_ops"))
    user_prompt = constraints.model_dump_json()
    if scraped_context:
        user_prompt = f"{user_prompt}\n\n--- SCRAPED RESEARCH CONTEXT ---\n{scraped_context}"
    user_prompt = append_feedback(user_prompt, feedback)
    raw_output = chat_fn(SYSTEM_PROMPT, user_prompt)
    return parse_json_response(raw_output, GTMSentiment)
