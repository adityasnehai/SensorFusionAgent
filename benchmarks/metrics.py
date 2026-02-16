from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import wasserstein_distance


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _extract_overlay_pair(visual_data: dict[str, Any], key: str) -> tuple[np.ndarray, np.ndarray]:
    points = visual_data.get(key) or []
    if not isinstance(points, list) or not points:
        return np.array([], dtype=float), np.array([], dtype=float)

    dataset_keys = sorted([k for k in points[0].keys() if k.startswith("dataset_")])
    if len(dataset_keys) < 2:
        return np.array([], dtype=float), np.array([], dtype=float)

    left_key, right_key = dataset_keys[0], dataset_keys[1]
    left_values: list[float] = []
    right_values: list[float] = []

    for item in points:
        left = item.get(left_key)
        right = item.get(right_key)
        if left is None or right is None:
            continue
        try:
            lx = float(left)
            ry = float(right)
        except Exception:
            continue
        if not (np.isfinite(lx) and np.isfinite(ry)):
            continue
        left_values.append(lx)
        right_values.append(ry)

    if len(left_values) < 16:
        return np.array([], dtype=float), np.array([], dtype=float)

    return np.array(left_values, dtype=float), np.array(right_values, dtype=float)


def _alignment_mae(fusion_report: dict[str, Any], metadata: dict[str, Any]) -> float:
    corrections = (
        (fusion_report.get("alignment_decisions") or {}).get("offset_corrections")
        or []
    )
    predicted = [
        float(item.get("offset_seconds", 0.0))
        for item in corrections
        if isinstance(item, dict) and str(item.get("dataset_id", "")) != "dataset1"
    ]

    if not predicted:
        return 0.0

    gt_map = metadata.get("ground_truth_offsets_seconds")
    scalar_gt = metadata.get("ground_truth_offset_seconds")

    errors: list[float] = []
    if isinstance(gt_map, dict):
        pred_map = {
            str(item.get("dataset_id")): float(item.get("offset_seconds", 0.0))
            for item in corrections
            if isinstance(item, dict)
        }
        for dataset_id, gt_value in gt_map.items():
            if str(dataset_id) in pred_map:
                try:
                    errors.append(abs(float(pred_map[str(dataset_id)]) - float(gt_value)))
                except Exception:
                    continue
    else:
        if scalar_gt is None:
            gt_value = 0.0
        else:
            try:
                gt_value = float(scalar_gt)
            except Exception:
                gt_value = 0.0
        errors = [abs(value - gt_value) for value in predicted]

    if not errors:
        return 0.0
    return float(np.mean(np.array(errors, dtype=float)))


def _wasserstein_similarity(visual_data: dict[str, Any]) -> float:
    left, right = _extract_overlay_pair(visual_data, "acc_magnitude_overlay")
    if len(left) == 0 or len(right) == 0:
        return 0.0

    distance = float(wasserstein_distance(left, right))
    scale = float(np.std(np.concatenate([left, right]))) + 1e-9
    similarity = float(np.exp(-distance / (3.0 * scale)))
    return _clip01(similarity)


def _dominant_frequency(signal: np.ndarray, sampling_rate_hz: float) -> float:
    if len(signal) < 16 or sampling_rate_hz <= 0:
        return 0.0
    centered = signal - float(np.mean(signal))
    fft = np.fft.rfft(centered)
    power = np.abs(fft) ** 2
    freqs = np.fft.rfftfreq(len(signal), d=1.0 / sampling_rate_hz)
    if len(power) <= 1:
        return 0.0
    idx = int(np.argmax(power[1:]) + 1)
    return float(freqs[idx])


def _frequency_similarity(visual_data: dict[str, Any], sampling_rate_hz: float) -> float:
    left, right = _extract_overlay_pair(visual_data, "acc_magnitude_overlay")
    if len(left) == 0 or len(right) == 0:
        return 0.0

    n = min(len(left), len(right), 2000)
    left = left[:n]
    right = right[:n]

    dom_left = _dominant_frequency(left, sampling_rate_hz)
    dom_right = _dominant_frequency(right, sampling_rate_hz)
    diff = abs(dom_left - dom_right)

    similarity = float(np.exp(-diff / (sampling_rate_hz / 10.0 + 1e-9)))
    return _clip01(similarity)


def _drift_stability(fusion_report: dict[str, Any], variance_reference: float = 0.0025) -> float:
    drift = fusion_report.get("drift_analysis") or {}
    trend = drift.get("offset_trend") or []
    offsets = []
    for item in trend:
        if not isinstance(item, dict):
            continue
        try:
            value = float(item.get("offset_seconds", 0.0))
        except Exception:
            continue
        if np.isfinite(value):
            offsets.append(value)

    if len(offsets) < 2:
        if str(drift.get("drift_type", "none")) == "none":
            return 1.0
        return 0.5

    variance = float(np.var(np.array(offsets, dtype=float)))
    normalized = 1.0 / (1.0 + variance / max(1e-9, variance_reference))
    return _clip01(normalized)


def compute_signal_metrics(
    *,
    fusion_report: dict[str, Any],
    visual_data: dict[str, Any],
    metadata: dict[str, Any],
    sampling_rate_hz: float,
    runtime_seconds: float,
    drift_variance_reference: float = 0.0025,
) -> dict[str, float]:
    alignment_mae = _alignment_mae(fusion_report, metadata)
    wasserstein_similarity = _wasserstein_similarity(visual_data)
    frequency_similarity = _frequency_similarity(visual_data, sampling_rate_hz)
    drift_stability = _drift_stability(fusion_report, variance_reference=drift_variance_reference)

    return {
        "alignment_mae": round(float(max(0.0, alignment_mae)), 6),
        "wasserstein_similarity": round(wasserstein_similarity, 6),
        "frequency_similarity": round(frequency_similarity, 6),
        "drift_stability": round(drift_stability, 6),
        "runtime_seconds": round(float(max(0.0, runtime_seconds)), 6),
    }


def compute_agent_metrics(
    *,
    hqscore_with_agent: float,
    hqscore_without_agent: float,
    predicted_confidence: float,
    chosen_strategy: str,
    best_strategy: str,
) -> dict[str, float]:
    improvement = float(hqscore_with_agent - hqscore_without_agent)
    calibration_error = abs(float(predicted_confidence) - float(hqscore_with_agent))
    strategy_accuracy = 1.0 if str(chosen_strategy) == str(best_strategy) else 0.0

    return {
        "hqscore_improvement": round(improvement, 6),
        "confidence_calibration_error": round(_clip01(calibration_error), 6),
        "strategy_selection_accuracy": round(strategy_accuracy, 6),
    }


def compute_final_scores(
    *,
    signal_metrics: dict[str, float],
    agent_metrics: dict[str, float],
    max_alignment_error_seconds: float = 1.0,
) -> dict[str, float]:
    alignment_mae = float(signal_metrics.get("alignment_mae", 0.0))
    normalized_alignment_mae = _clip01(alignment_mae / max(1e-9, max_alignment_error_seconds))

    signal_score = float(
        np.mean(
            [
                1.0 - normalized_alignment_mae,
                float(signal_metrics.get("wasserstein_similarity", 0.0)),
                float(signal_metrics.get("frequency_similarity", 0.0)),
                float(signal_metrics.get("drift_stability", 0.0)),
            ]
        )
    )
    signal_score = _clip01(signal_score)

    improvement = float(agent_metrics.get("hqscore_improvement", 0.0))
    normalized_improvement = _clip01((improvement + 1.0) / 2.0)

    agent_score = float(
        np.mean(
            [
                normalized_improvement,
                1.0 - _clip01(float(agent_metrics.get("confidence_calibration_error", 1.0))),
                _clip01(float(agent_metrics.get("strategy_selection_accuracy", 0.0))),
            ]
        )
    )
    agent_score = _clip01(agent_score)

    final_score = _clip01(0.6 * signal_score + 0.4 * agent_score)

    return {
        "final_score": round(final_score, 6),
        "signal_score": round(signal_score, 6),
        "agent_score": round(agent_score, 6),
    }
