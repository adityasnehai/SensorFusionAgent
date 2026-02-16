from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.core.modality_registry import MODALITY_REGISTRY
from app.core.task_inference import infer_task_context


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


def _acc_magnitude(df: pd.DataFrame) -> np.ndarray:
    required = ("acc_x", "acc_y", "acc_z")
    if not all(col in df.columns for col in required):
        return np.array([], dtype=float)
    numeric = df[list(required)].apply(pd.to_numeric, errors="coerce")
    mag = np.sqrt((numeric ** 2).sum(axis=1)).replace([np.inf, -np.inf], np.nan).dropna()
    return mag.to_numpy(dtype=float)


def _peak_correlation(df_a: pd.DataFrame, df_b: pd.DataFrame) -> float:
    x = _acc_magnitude(df_a)
    y = _acc_magnitude(df_b)

    n = min(len(x), len(y))
    if n < 32:
        return 0.5

    x = x[:n] - float(np.mean(x[:n]))
    y = y[:n] - float(np.mean(y[:n]))
    denom = float(np.linalg.norm(x) * np.linalg.norm(y)) + 1e-9
    if denom <= 1e-9:
        return 0.5

    corr = np.correlate(x, y, mode="full")
    peak = float(np.max(np.abs(corr)) / denom)
    return float(max(0.0, min(1.0, peak)))


def detect_modalities(datasets: list[pd.DataFrame]) -> list[str]:
    found: set[str] = set()
    for df in datasets:
        for modality, cfg in MODALITY_REGISTRY.items():
            if any(col in df.columns for col in cfg["columns"]):
                found.add(modality)
    return sorted(found)


def build_adaptive_context(datasets: list[pd.DataFrame]) -> dict[str, Any]:
    modalities = detect_modalities(datasets)
    rates = [_estimate_sampling_rate(df) for df in datasets]
    rates = [rate for rate in rates if rate > 0]

    durations = []
    for df in datasets:
        if "timestamp" not in df.columns or len(df) < 2:
            continue
        ts = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed").dropna()
        if ts.empty:
            continue
        durations.append(float(max(0.0, (ts.max() - ts.min()).total_seconds())))

    task = infer_task_context(
        datasets,
        detected_modalities=modalities,
    )

    return {
        "modalities": modalities,
        "sampling_rates_hz": rates,
        "duration_seconds": float(np.mean(durations)) if durations else 0.0,
        "task_type": str(task.get("predicted_task", "Unknown")),
        "drift_flag": False,
        "user_override_flag": False,
        "task_inference": task,
    }


def choose_alignment_strategy(datasets: list[pd.DataFrame]) -> dict[str, Any]:
    rates = [_estimate_sampling_rate(df) for df in datasets]
    valid_rates = [rate for rate in rates if rate > 0]
    spread = float(np.std(valid_rates)) if len(valid_rates) >= 2 else 0.0

    pair_peaks = []
    for idx in range(1, len(datasets)):
        pair_peaks.append(_peak_correlation(datasets[0], datasets[idx]))
    mean_peak = float(np.mean(pair_peaks)) if pair_peaks else 0.5

    # Current production backend runs classical alignment mode only.
    # Keep confidence as a quality proxy so benchmark agent metrics remain informative.
    confidence = max(0.55, min(0.95, 0.55 + (mean_peak - 0.5) + max(0.0, 0.2 - spread / 30.0)))
    return {
        "alignment_mode": "classical",
        "strategy_confidence": round(float(confidence), 4),
        "reason": (
            f"Classical alignment selected (production mode). "
            f"Signal peak correlation={mean_peak:.3f}, sampling-rate spread={spread:.3f}."
        ),
    }
