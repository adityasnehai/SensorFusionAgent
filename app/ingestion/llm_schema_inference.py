from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

import numpy as np
import pandas as pd

from app.core.modality_registry import MODALITY_REGISTRY
from app.llm.client import get_llm_client

LLM_CANONICAL_LABELS = {
    "acc_x",
    "acc_y",
    "acc_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "mag_x",
    "mag_y",
    "mag_z",
    "gps_lat",
    "gps_lon",
    "heart_rate",
    "pressure",
    "light_lux",
    "proximity",
    "unknown",
}

LLM_CANONICAL_ALIASES = {
    "barometer": "pressure",
    "light_sensor": "light_lux",
}


def _env_flag(name: str, default: str = "0") -> bool:
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None

    text = text.strip()
    try:
        loaded = json.loads(text)
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None

    try:
        loaded = json.loads(match.group(0))
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        return None


def _python_float(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    if not np.isfinite(number):
        return None
    return number


def _column_stats(df: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}

    for col in columns:
        numeric = pd.to_numeric(df[col], errors="coerce")
        valid = numeric.dropna()
        if valid.empty:
            continue

        stats[col] = {
            "mean": round(float(valid.mean()), 6),
            "std": round(float(valid.std(ddof=0)), 6),
            "min": round(float(valid.min()), 6),
            "max": round(float(valid.max()), 6),
        }

    return stats


def _preview_rows(df: pd.DataFrame, columns: list[str], max_rows: int = 5) -> list[dict[str, Any]]:
    preview = df[columns].head(max_rows).copy()
    preview = preview.replace({np.nan: None})

    rows: list[dict[str, Any]] = []
    for record in preview.to_dict(orient="records"):
        normalized: dict[str, Any] = {}
        for key, value in record.items():
            if isinstance(value, (np.integer, np.floating)):
                normalized[key] = float(value)
            elif pd.isna(value):
                normalized[key] = None
            else:
                normalized[key] = value
        rows.append(normalized)

    return rows


def infer_schema_with_llm_fallback(
    df: pd.DataFrame,
    *,
    timestamp_column: str,
    rule_confidence: float,
) -> dict[str, Any]:
    """Attempt LLM schema inference when rule-based confidence is low.

    The request is opt-in via env flags:
    - LLM_SCHEMA_INFERENCE_ENABLED=1 enables the call
    - LLM_SCHEMA_SEND_PREVIEW=1 includes first rows in prompt
    """
    if rule_confidence >= 0.85:
        return {
            "accepted": False,
            "schema_mapping": {},
            "confidence": round(float(rule_confidence), 4),
            "reasoning_summary": "Rule-based confidence is already high.",
            "method": "rule_based",
        }

    if not _env_flag("LLM_SCHEMA_INFERENCE_ENABLED", "0"):
        return {
            "accepted": False,
            "schema_mapping": {},
            "confidence": round(float(rule_confidence), 4),
            "reasoning_summary": "LLM schema inference disabled by configuration.",
            "method": "rule_based",
        }

    columns = [col for col in df.columns if col != timestamp_column]
    if not columns:
        return {
            "accepted": False,
            "schema_mapping": {},
            "confidence": round(float(rule_confidence), 4),
            "reasoning_summary": "No non-timestamp columns available for schema inference.",
            "method": "rule_based",
        }

    columns = columns[:40]
    stats = _column_stats(df, columns)
    send_preview = _env_flag("LLM_SCHEMA_SEND_PREVIEW", "0")
    preview = _preview_rows(df, columns, max_rows=5) if send_preview else []

    modality_registry = {
        modality: cfg["columns"]
        for modality, cfg in MODALITY_REGISTRY.items()
    }

    user_prompt = (
        "Infer sensor schema mapping from ambiguous columns.\\n"
        "Return strict JSON with keys: schema_mapping, confidence, reasoning_summary.\\n"
        "Rules:\\n"
        "- Map each provided column to exactly one canonical label or unknown.\\n"
        "- Do not map two columns to the same canonical label (unknown can repeat).\\n"
        "- Use numeric ranges and axis grouping hints where possible.\\n"
        "- Confidence must be between 0 and 1.\\n"
        f"Allowed canonical labels: {sorted(LLM_CANONICAL_LABELS)}\\n"
        f"Known modality registry: {json.dumps(modality_registry)}\\n"
        f"Columns: {json.dumps(columns)}\\n"
        f"Basic stats: {json.dumps(stats)}\\n"
        f"Preview rows (may be empty when data sharing is restricted): {json.dumps(preview)}"
    )

    try:
        client = get_llm_client()
    except Exception:
        return {
            "accepted": False,
            "schema_mapping": {},
            "confidence": round(float(rule_confidence), 4),
            "reasoning_summary": "LLM client unavailable or API key missing.",
            "method": "rule_based",
        }

    model = os.getenv("LLM_SCHEMA_MODEL", "gpt-4o-mini")
    timeout_seconds = max(5, int(os.getenv("LLM_SCHEMA_TIMEOUT_SECONDS", "18")))

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict schema inference engine. Respond with valid JSON only.",
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            timeout=timeout_seconds,
        )
        content = response.choices[0].message.content or ""
    except Exception:
        return {
            "accepted": False,
            "schema_mapping": {},
            "confidence": round(float(rule_confidence), 4),
            "reasoning_summary": "LLM schema call failed or timed out; fallback to rule-based mapping.",
            "method": "rule_based",
        }

    payload = _extract_json_object(content)
    if not payload:
        return {
            "accepted": False,
            "schema_mapping": {},
            "confidence": round(float(rule_confidence), 4),
            "reasoning_summary": "LLM returned non-JSON output.",
            "method": "rule_based",
        }

    raw_mapping = payload.get("schema_mapping")
    if not isinstance(raw_mapping, dict):
        return {
            "accepted": False,
            "schema_mapping": {},
            "confidence": round(float(rule_confidence), 4),
            "reasoning_summary": "LLM output missing schema_mapping object.",
            "method": "rule_based",
        }

    confidence = _python_float(payload.get("confidence"))
    confidence = 0.0 if confidence is None else confidence
    confidence = max(0.0, min(1.0, confidence))

    normalized_mapping: Dict[str, str] = {}
    used_targets: set[str] = set()

    for column in columns:
        raw_label = raw_mapping.get(column, "unknown")
        if not isinstance(raw_label, str):
            raw_label = "unknown"

        label = raw_label.strip().lower()
        label = LLM_CANONICAL_ALIASES.get(label, label)
        if label not in LLM_CANONICAL_LABELS:
            label = "unknown"

        if label != "unknown":
            if label in used_targets:
                return {
                    "accepted": False,
                    "schema_mapping": {},
                    "confidence": round(float(rule_confidence), 4),
                    "reasoning_summary": (
                        "Rejected LLM schema mapping due to duplicate canonical assignments."
                    ),
                    "method": "rule_based",
                }
            used_targets.add(label)

        normalized_mapping[column] = label

    mapped_targets = {value for value in normalized_mapping.values() if value != "unknown"}
    gps_targets = mapped_targets.intersection({"gps_lat", "gps_lon"})
    if len(gps_targets) == 1:
        return {
            "accepted": False,
            "schema_mapping": {},
            "confidence": round(float(rule_confidence), 4),
            "reasoning_summary": "Rejected LLM mapping: gps_lat/gps_lon must be inferred as a pair.",
            "method": "rule_based",
        }

    if confidence < 0.65 or confidence <= rule_confidence:
        return {
            "accepted": False,
            "schema_mapping": {},
            "confidence": round(float(rule_confidence), 4),
            "reasoning_summary": "LLM confidence too low compared to rule-based inference.",
            "method": "rule_based",
        }

    reasoning_summary = payload.get("reasoning_summary")
    if not isinstance(reasoning_summary, str) or not reasoning_summary.strip():
        reasoning_summary = "LLM inferred mappings from column semantics and numeric profiles."

    return {
        "accepted": True,
        "schema_mapping": normalized_mapping,
        "confidence": round(float(confidence), 4),
        "reasoning_summary": reasoning_summary.strip(),
        "method": "llm",
    }
