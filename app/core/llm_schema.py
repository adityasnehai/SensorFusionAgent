from __future__ import annotations

import json
import re
from typing import Any

from app.llm.client import get_llm_client


ALLOWED_LABELS = {
    "acc_x",
    "acc_y",
    "acc_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "timestamp",
    "unknown",
}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None

    text = text.strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None

    try:
        payload = json.loads(match.group(0))
    except Exception:
        return None

    return payload if isinstance(payload, dict) else None


def infer_schema_with_llm(column_list: list[str]) -> dict[str, str]:
    try:
        client = get_llm_client()
    except Exception:
        return {}

    prompt = (
        "You are a schema inference engine.\n"
        "Map each column to one canonical name from:\n"
        "acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, timestamp, unknown.\n"
        "Return JSON mapping only.\n"
        f"Columns: {json.dumps(column_list, ensure_ascii=True)}"
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

    payload = _extract_json_object(content)
    if not payload:
        return {}

    normalized: dict[str, str] = {}
    for col in column_list:
        mapped = payload.get(col, "unknown")
        if not isinstance(mapped, str):
            mapped = "unknown"
        mapped = mapped.strip().lower()
        if mapped not in ALLOWED_LABELS:
            mapped = "unknown"
        normalized[str(col)] = mapped

    return normalized
