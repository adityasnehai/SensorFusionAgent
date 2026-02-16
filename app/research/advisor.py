from __future__ import annotations

import json
import re
from typing import Any

from app.llm.client import get_llm_client


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None

    text = text.strip()
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None

    try:
        loaded = json.loads(match.group(0))
    except Exception:
        return None

    return loaded if isinstance(loaded, dict) else None


def extract_research_patterns(fingerprint: dict[str, Any], papers: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        client = get_llm_client()
    except Exception:
        return {}

    prompt = (
        "You are a research extraction engine.\n"
        "Given dataset fingerprint and cited papers, extract common harmonization guidance.\n"
        "Return STRICT JSON with keys:\n"
        "recommended_sampling_rate, filtering, window_size_seconds, fusion_strategy.\n"
        f"Fingerprint: {json.dumps(fingerprint, ensure_ascii=True)}\n"
        f"Papers: {json.dumps(papers, ensure_ascii=True)}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            timeout=20,
        )
        content = response.choices[0].message.content or ""
    except Exception:
        return {}

    parsed = _extract_json_object(content)
    if not parsed:
        return {}

    # Keep permissive structure for backward compatibility with existing /suggest contract.
    return parsed
