"""Optional LLM-generated research notes (OpenAI-compatible chat completions API)."""

from __future__ import annotations

import json
import logging

import requests

from . import config

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a cautious financial research analyst. For each asset provided, write a "
    "concise 1-2 sentence research note explaining why its metrics make it a speculative "
    "buy candidate this week and the key risk to watch. Use only the data provided; do "
    "not invent news or numbers. Respond with a JSON object mapping each symbol to its note."
)


def add_ai_summaries(items: list[dict], asset_class: str, session: requests.Session | None = None) -> bool:
    """Attach an ``ai_summary`` to each item. Returns True if summaries were added.

    Does nothing when ``OPENAI_API_KEY`` is not configured. Failures are logged and
    never break the research run.
    """
    if not config.OPENAI_API_KEY or not items:
        return False
    fields = (
        "symbol", "name", "price", "change_1d", "change_1w", "change_1m", "change_3m",
        "rsi", "volume_ratio", "market_cap_rank", "risk", "score", "rationale",
    )
    payload = [{key: item[key] for key in fields if key in item} for item in items]
    session = session or requests.Session()
    try:
        response = session.post(
            f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": "Bearer " + config.OPENAI_API_KEY},
            json={
                "model": config.OPENAI_MODEL,
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Asset class: {asset_class}\n{json.dumps(payload)}"},
                ],
            },
            timeout=config.HTTP_TIMEOUT * 2,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        notes = json.loads(content)
    except Exception as exc:
        log.warning("AI summary generation failed for %s: %s", asset_class, exc)
        return False

    if not isinstance(notes, dict):
        return False
    added = False
    for item in items:
        note = notes.get(item["symbol"])
        if isinstance(note, str) and note.strip():
            item["ai_summary"] = note.strip()
            added = True
    return added
