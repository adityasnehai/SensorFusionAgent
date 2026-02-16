from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

TASKS = (
    "Human Activity Recognition",
    "Gait Analysis",
    "Free-living Monitoring",
    "Driving Behavior",
    "Health Monitoring",
    "Environmental Sensing",
    "Unknown",
)

SUGGESTED_WINDOWS = {
    "Human Activity Recognition": 2.5,
    "Gait Analysis": 4.0,
    "Free-living Monitoring": 10.0,
    "Driving Behavior": 5.0,
    "Health Monitoring": 8.0,
    "Environmental Sensing": 30.0,
    "Unknown": None,
}

SUGGESTED_RATES = {
    "Human Activity Recognition": 50.0,
    "Gait Analysis": 100.0,
    "Free-living Monitoring": 25.0,
    "Driving Behavior": 20.0,
    "Health Monitoring": 25.0,
    "Environmental Sensing": 1.0,
    "Unknown": None,
}

HQSCORE_WEIGHT_PROFILES = {
    "Human Activity Recognition": "temporal_spectral",
    "Gait Analysis": "temporal_spectral",
    "Free-living Monitoring": "stability_temporal",
    "Driving Behavior": "stability_temporal",
    "Health Monitoring": "missingness_stability",
    "Environmental Sensing": "distribution_coverage",
    "Unknown": "balanced",
}


def _estimate_sampling_rate(df: pd.DataFrame) -> float:
    if "timestamp" not in df.columns:
        return 0.0

    ts = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed")
    diffs = ts.diff().dt.total_seconds().dropna()
    if len(diffs) == 0:
        return 0.0

    median = diffs.median()
    if median <= 0:
        return 0.0

    return float(1.0 / median)


def _duration_seconds(df: pd.DataFrame) -> float:
    if "timestamp" not in df.columns or len(df) < 2:
        return 0.0

    ts = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed").dropna()
    if ts.empty:
        return 0.0

    return float(max(0.0, (ts.max() - ts.min()).total_seconds()))


def _numeric_variance_score(df: pd.DataFrame) -> float:
    numeric = df.select_dtypes(include=[np.number]).copy()
    if numeric.empty:
        return 0.0

    for col in list(numeric.columns):
        numeric[col] = pd.to_numeric(numeric[col], errors="coerce")

    variances = numeric.var(axis=0, ddof=0).replace([np.inf, -np.inf], np.nan).dropna()
    if variances.empty:
        return 0.0

    median_variance = float(variances.median())
    return float(max(0.0, min(1.0, np.tanh(median_variance / 5.0))))


def _safe_mean(values: list[float]) -> float:
    valid = [v for v in values if np.isfinite(v)]
    if not valid:
        return 0.0
    return float(sum(valid) / len(valid))


def infer_task_context(
    dataframes: list[pd.DataFrame],
    *,
    detected_modalities: list[str] | None = None,
    llm_reasoning_summary: str | None = None,
    research_context_hint: str | None = None,
) -> dict[str, Any]:
    modalities = sorted(set(detected_modalities or []))

    sampling_rates = [_estimate_sampling_rate(df) for df in dataframes]
    avg_rate = _safe_mean(sampling_rates)

    durations = [_duration_seconds(df) for df in dataframes]
    avg_duration = _safe_mean(durations)

    variance_scores = [_numeric_variance_score(df) for df in dataframes]
    avg_variance = _safe_mean(variance_scores)

    has_acc = "accelerometer" in modalities
    has_gyro = "gyroscope" in modalities
    has_gps = "gps" in modalities
    has_hr = "heart_rate" in modalities
    has_env = any(m in modalities for m in ("barometer", "light", "proximity"))

    scores = {task: 0.05 for task in TASKS if task != "Unknown"}

    if has_acc and has_gyro:
        scores["Human Activity Recognition"] += 0.35
        if 20 <= avg_rate <= 120:
            scores["Human Activity Recognition"] += 0.25
        if avg_duration <= 4 * 3600:
            scores["Human Activity Recognition"] += 0.08

    if has_acc and 40 <= avg_rate <= 200:
        scores["Gait Analysis"] += 0.30
        if avg_variance >= 0.2:
            scores["Gait Analysis"] += 0.12

    if has_acc and has_gyro and avg_duration >= 3 * 3600:
        scores["Free-living Monitoring"] += 0.26
    if avg_duration >= 8 * 3600:
        scores["Free-living Monitoring"] += 0.15

    if has_gps:
        scores["Driving Behavior"] += 0.22
        if 5 <= avg_rate <= 30:
            scores["Driving Behavior"] += 0.14
        if has_acc and has_gyro:
            scores["Driving Behavior"] += 0.12

    if has_hr:
        scores["Health Monitoring"] += 0.28
        if avg_duration >= 30 * 60:
            scores["Health Monitoring"] += 0.16
        if has_acc:
            scores["Health Monitoring"] += 0.10

    if has_env:
        scores["Environmental Sensing"] += 0.30
        if avg_rate <= 5:
            scores["Environmental Sensing"] += 0.18
        if not (has_acc or has_gyro):
            scores["Environmental Sensing"] += 0.12

    if isinstance(research_context_hint, str) and research_context_hint.strip():
        hint = research_context_hint.lower()
        if "har" in hint or "activity" in hint:
            scores["Human Activity Recognition"] += 0.05
        if "gait" in hint:
            scores["Gait Analysis"] += 0.05
        if "driv" in hint:
            scores["Driving Behavior"] += 0.05
        if "health" in hint:
            scores["Health Monitoring"] += 0.05
        if "environment" in hint:
            scores["Environmental Sensing"] += 0.05

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_task, best_score = ranked[0] if ranked else ("Unknown", 0.0)
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if best_score < 0.2:
        predicted_task = "Unknown"
        confidence = 0.3
    else:
        predicted_task = best_task
        margin = max(0.0, best_score - second_score)
        confidence = min(0.97, 0.45 + best_score * 0.35 + margin * 0.3)

    confidence = round(float(max(0.0, min(1.0, confidence))), 4)

    modality_text = ", ".join(modalities) if modalities else "no known modalities"
    rate_text = f"{avg_rate:.2f}Hz" if avg_rate > 0 else "unknown rate"
    duration_text = f"{avg_duration/60:.1f} minutes" if avg_duration > 0 else "unknown duration"

    reasoning_parts = [
        f"Detected modalities: {modality_text}.",
        f"Average sampling rate: {rate_text}; average duration: {duration_text}.",
    ]
    if llm_reasoning_summary:
        reasoning_parts.append(f"Schema inference note: {llm_reasoning_summary}")
    reasoning = " ".join(reasoning_parts)

    return {
        "predicted_task": predicted_task,
        "confidence": confidence,
        "reasoning": reasoning,
        "suggested_window_seconds": SUGGESTED_WINDOWS.get(predicted_task),
        "suggested_sampling_rate_hz": SUGGESTED_RATES.get(predicted_task),
        "hqscore_weight_profile": HQSCORE_WEIGHT_PROFILES.get(predicted_task, "balanced"),
        "modalities": modalities,
        "average_sampling_rate_hz": round(avg_rate, 4),
        "average_duration_seconds": round(avg_duration, 2),
    }
