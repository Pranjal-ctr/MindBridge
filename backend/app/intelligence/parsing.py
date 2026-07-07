"""
Defensive JSON parsing for structured AI responses.

Even with provider JSON mode, a fallback provider may return fenced or
prefixed JSON -- so every structured feature parses through here (same
fence-stripping the memory extractor uses).
"""

from __future__ import annotations

import json


def parse_json_response(text: str | None) -> dict:
    """Parse a model response into a dict. Raises ValueError if not a JSON object."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"model response is not valid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"model response is not a JSON object: {type(data).__name__}")
    return data
