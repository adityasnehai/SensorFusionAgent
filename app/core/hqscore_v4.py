from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from scipy import signal
from scipy.stats import entropy, wasserstein_distance

from app.core.modality_registry import MODALITY_REGISTRY


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _numeric_series(df: pd.DataFrame, columns: List[str]) -> pd.Series:
    if not all(col in df.columns for col in columns):
        return pd.Series(dtype=float)
    numeric = df[columns].apply(pd.to_numeric, errors="coerce")
    magnitude = np.sqrt((numeric ** 2).sum(axis=1))
    return pd.Series(magnitude).replace([np.inf, -np.inf], np.nan).dropna()


def _paired_values(a: pd.Series, b: pd.Series, max_points: int = 2000) -> tuple[np.ndarray, np.ndarray]:
    if len(a) == 0 or len(b) == 0:
        return np.array([], dtype=float), np.array([], dtype=float)

    n = min(len(a), len(b), max_points)
    if n < 16:
        return np.array([], dtype=float), np.array([], dtype=float)

    x = a.iloc[:n].to_numpy(dtype=float)
    y = b.iloc[:n].to_numpy(dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 16:
        return np.array([], dtype=float), np.array([], dtype=float)

    return x[mask], y[mask]


def _symmetric_kl_similarity(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    low = float(min(np.min(x), np.min(y)))
    high = float(max(np.max(x), np.max(y)))
    if low == high:
        return 1.0, 0.0

    bins = np.linspace(low, high, 48)
    px, _ = np.histogram(x, bins=bins, density=True)
    py, _ = np.histogram(y, bins=bins, density=True)

    px = px + 1e-9
    py = py + 1e-9
    px = px / np.sum(px)
    py = py / np.sum(py)

    kl = 0.5 * float(entropy(px, py) + entropy(py, px))
    similarity = float(np.exp(-kl))
    return _clip01(similarity), kl


def _wasserstein_similarity(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    dist = float(wasserstein_distance(x, y))
    scale = float(np.std(np.concatenate([x, y]))) + 1e-6
    similarity = float(np.exp(-dist / (3.0 * scale)))
    return _clip01(similarity), dist


def _dominant_frequency(power: np.ndarray, freqs: np.ndarray) -> float:
    if len(power) <= 1:
        return 0.0
    idx = int(np.argmax(power[1:]) + 1)
    return float(freqs[idx])


def _spectral_pair_similarity(x: np.ndarray, y: np.ndarray, sampling_rate_hz: float) -> tuple[float, float, float]:
    n = min(len(x), len(y), 2000)
    if n < 32 or sampling_rate_hz <= 0:
        return 0.5, 0.5, 0.0

    x = x[:n]
    y = y[:n]

    window = np.hanning(n)
    fx = np.fft.rfft((x - np.mean(x)) * window)
    fy = np.fft.rfft((y - np.mean(y)) * window)
    px = np.abs(fx) ** 2
    py = np.abs(fy) ** 2
    freqs = np.fft.rfftfreq(n, d=1.0 / sampling_rate_hz)

    dom_x = _dominant_frequency(px, freqs)
    dom_y = _dominant_frequency(py, freqs)

    dom_diff = abs(dom_x - dom_y)
    dom_similarity = float(np.exp(-dom_diff / (sampling_rate_hz / 12.0 + 1e-6)))

    nperseg = min(256, n)
    _, coherence = signal.coherence(x, y, fs=sampling_rate_hz, nperseg=nperseg)
    coherence_score = float(np.nanmean(coherence)) if len(coherence) else 0.0
    coherence_score = _clip01(coherence_score)

    score = _clip01(0.5 * dom_similarity + 0.5 * coherence_score)
    return score, coherence_score, dom_similarity


def _normalized_cross_corr(x: np.ndarray, y: np.ndarray) -> tuple[float, int]:
    if len(x) != len(y) or len(x) < 16:
        return 0.0, 0

    x = x - np.mean(x)
    y = y - np.mean(y)
    denom = float(np.linalg.norm(x) * np.linalg.norm(y)) + 1e-9
    if denom <= 1e-9:
        return 0.0, 0

    corr = np.correlate(x, y, mode="full")
    idx = int(np.argmax(np.abs(corr)))
    lag = idx - (len(x) - 1)
    peak = float(np.abs(corr[idx]) / denom)
    return _clip01(peak), lag


def _snr_estimate(x: np.ndarray) -> float:
    if len(x) < 10:
        return 1.0

    window = min(31, max(5, len(x) // 20))
    if window % 2 == 0:
        window += 1

    kernel = np.ones(window, dtype=float) / float(window)
    smooth = np.convolve(x, kernel, mode="same")
    noise = x - smooth

    signal_power = float(np.var(smooth))
    noise_power = float(np.var(noise)) + 1e-9
    return signal_power / noise_power


def _snr_consistency(x: np.ndarray, y: np.ndarray) -> float:
    snr_x = _snr_estimate(x)
    snr_y = _snr_estimate(y)
    delta = abs(np.log10(snr_x + 1.0) - np.log10(snr_y + 1.0))
    return _clip01(1.0 - min(1.0, delta / 2.0))


def _weighted_missingness_penalty(merged_df: pd.DataFrame) -> float:
    total_weight = float(sum(cfg["weight"] for cfg in MODALITY_REGISTRY.values())) + 1e-9
    weighted_missing = 0.0

    for _, cfg in MODALITY_REGISTRY.items():
        weight = float(cfg["weight"])
        cols = [col for col in cfg["columns"] if col in merged_df.columns]
        if not cols:
            missing_ratio = 1.0
        else:
            missing_ratio = float(merged_df[cols].isna().mean().mean())
        weighted_missing += weight * missing_ratio

    return _clip01(weighted_missing / total_weight)


def _sensor_coverage(merged_df: pd.DataFrame) -> float:
    total_weight = float(sum(cfg["weight"] for cfg in MODALITY_REGISTRY.values())) + 1e-9
    covered_weight = 0.0

    for _, cfg in MODALITY_REGISTRY.items():
        cols = [col for col in cfg["columns"] if col in merged_df.columns]
        if cols:
            covered_weight += float(cfg["weight"])

    return _clip01(covered_weight / total_weight)


def _resolve_weights(task_inference: dict | None) -> dict[str, float]:
    default_weights = {
        "distribution_similarity": 0.25,
        "spectral_similarity": 0.20,
        "temporal_alignment_strength": 0.20,
        "missingness": 0.15,
        "sensor_coverage": 0.10,
        "stability_factor": 0.10,
    }
    if not task_inference:
        return default_weights

    predicted_task = str(task_inference.get("predicted_task", "")).strip().lower()
    profile = str(task_inference.get("hqscore_weight_profile", "")).strip().lower()

    if "human activity" in predicted_task or "gait" in predicted_task or profile == "temporal_spectral":
        return {
            "distribution_similarity": 0.22,
            "spectral_similarity": 0.24,
            "temporal_alignment_strength": 0.24,
            "missingness": 0.13,
            "sensor_coverage": 0.07,
            "stability_factor": 0.10,
        }
    if "driving" in predicted_task or profile == "stability_temporal":
        return {
            "distribution_similarity": 0.20,
            "spectral_similarity": 0.17,
            "temporal_alignment_strength": 0.24,
            "missingness": 0.13,
            "sensor_coverage": 0.08,
            "stability_factor": 0.18,
        }
    if "health" in predicted_task or profile == "missingness_stability":
        return {
            "distribution_similarity": 0.21,
            "spectral_similarity": 0.16,
            "temporal_alignment_strength": 0.18,
            "missingness": 0.22,
            "sensor_coverage": 0.11,
            "stability_factor": 0.12,
        }
    if "environment" in predicted_task or profile == "distribution_coverage":
        return {
            "distribution_similarity": 0.30,
            "spectral_similarity": 0.14,
            "temporal_alignment_strength": 0.14,
            "missingness": 0.12,
            "sensor_coverage": 0.20,
            "stability_factor": 0.10,
        }

    return default_weights


def compute_hqscore_v4(
    merged_df: pd.DataFrame,
    resampled: List[pd.DataFrame],
    sampling_rate_hz: float,
    drift_analysis: dict,
    task_inference: dict | None = None,
    disable_advanced: bool = False,
    limited_modality: bool = False,
) -> dict:
    if not resampled:
        return {
            "overall": 0.0,
            "components": {
                "distribution_similarity": 0.0,
                "spectral_similarity": 0.0,
                "temporal_alignment_strength": 0.0,
                "missingness_penalty": 1.0,
                "sensor_coverage": 0.0,
                "stability_factor": 0.0,
            },
            "advanced_metrics": {
                "kl_divergence": 0.0,
                "wasserstein_distance": 0.0,
                "spectral_coherence_score": 0.0,
                "dominant_frequency_similarity": 0.0,
                "cross_correlation_peak_strength": 0.0,
                "snr_consistency": 0.0,
            },
        }

    distribution_scores = []
    kl_values = []
    wasserstein_values = []

    spectral_scores = []
    coherence_values = []
    dom_freq_values = []

    temporal_scores = []
    peak_values = []

    snr_scores = []

    pair_signals = []

    for i in range(len(resampled)):
        for j in range(i + 1, len(resampled)):
            left_acc = _numeric_series(resampled[i], ["acc_x", "acc_y", "acc_z"])
            right_acc = _numeric_series(resampled[j], ["acc_x", "acc_y", "acc_z"])
            x, y = _paired_values(left_acc, right_acc)
            if len(x) >= 16:
                pair_signals.append((x, y))

            if not limited_modality:
                left_gyro = _numeric_series(resampled[i], ["gyro_x", "gyro_y", "gyro_z"])
                right_gyro = _numeric_series(resampled[j], ["gyro_x", "gyro_y", "gyro_z"])
                gx, gy = _paired_values(left_gyro, right_gyro)
                if len(gx) >= 16:
                    pair_signals.append((gx, gy))

    for x, y in pair_signals:
        kl_similarity, kl_value = _symmetric_kl_similarity(x, y)
        w_similarity, w_value = _wasserstein_similarity(x, y)
        distribution_scores.append(0.5 * kl_similarity + 0.5 * w_similarity)
        kl_values.append(kl_value)
        wasserstein_values.append(w_value)

        spectral_score, coherence_score, dom_similarity = _spectral_pair_similarity(
            x,
            y,
            sampling_rate_hz,
        )
        spectral_scores.append(spectral_score)
        coherence_values.append(coherence_score)
        dom_freq_values.append(dom_similarity)

        peak, lag = _normalized_cross_corr(x, y)
        lag_score = 1.0 / (1.0 + abs(float(lag)) / max(1.0, 0.05 * len(x)))
        temporal_scores.append(_clip01(0.75 * peak + 0.25 * lag_score))
        peak_values.append(peak)

        snr_scores.append(_snr_consistency(x, y))

    distribution_similarity = float(np.mean(distribution_scores)) if distribution_scores else 0.55
    spectral_similarity = float(np.mean(spectral_scores)) if spectral_scores else 0.5
    temporal_alignment_strength = float(np.mean(temporal_scores)) if temporal_scores else 0.5
    snr_consistency = float(np.mean(snr_scores)) if snr_scores else 0.5

    if disable_advanced:
        spectral_similarity = min(spectral_similarity, 0.5)
        temporal_alignment_strength = min(temporal_alignment_strength, 0.55)
        snr_consistency = min(snr_consistency, 0.5)

    missingness_penalty = _weighted_missingness_penalty(merged_df)
    sensor_coverage = _sensor_coverage(merged_df)

    stability_from_drift = _clip01(float(drift_analysis.get("stability_score", 0.6)))
    stability_factor = _clip01(0.7 * stability_from_drift + 0.3 * snr_consistency)

    weights = _resolve_weights(task_inference)
    if limited_modality:
        # Shift emphasis away from spectral/temporal terms when only one modality exists.
        weights = {
            "distribution_similarity": 0.34,
            "spectral_similarity": 0.08,
            "temporal_alignment_strength": 0.10,
            "missingness": 0.20,
            "sensor_coverage": 0.20,
            "stability_factor": 0.08,
        }
    overall = (
        weights["distribution_similarity"] * distribution_similarity
        + weights["spectral_similarity"] * spectral_similarity
        + weights["temporal_alignment_strength"] * temporal_alignment_strength
        + weights["missingness"] * (1.0 - missingness_penalty)
        + weights["sensor_coverage"] * sensor_coverage
        + weights["stability_factor"] * stability_factor
    )
    overall = _clip01(overall)

    return {
        "overall": round(float(overall), 4),
        "components": {
            "distribution_similarity": round(_clip01(distribution_similarity), 4),
            "spectral_similarity": round(_clip01(spectral_similarity), 4),
            "temporal_alignment_strength": round(_clip01(temporal_alignment_strength), 4),
            "missingness_penalty": round(_clip01(missingness_penalty), 4),
            "sensor_coverage": round(_clip01(sensor_coverage), 4),
            "stability_factor": round(_clip01(stability_factor), 4),
        },
        "advanced_metrics": {
            "kl_divergence": round(float(np.mean(kl_values)) if kl_values else 0.0, 6),
            "wasserstein_distance": round(float(np.mean(wasserstein_values)) if wasserstein_values else 0.0, 6),
            "spectral_coherence_score": round(float(np.mean(coherence_values)) if coherence_values else 0.0, 6),
            "dominant_frequency_similarity": round(float(np.mean(dom_freq_values)) if dom_freq_values else 0.0, 6),
            "cross_correlation_peak_strength": round(float(np.mean(peak_values)) if peak_values else 0.0, 6),
            "snr_consistency": round(float(snr_consistency), 6),
            "weight_distribution_similarity": round(float(weights["distribution_similarity"]), 4),
            "weight_spectral_similarity": round(float(weights["spectral_similarity"]), 4),
            "weight_temporal_alignment_strength": round(float(weights["temporal_alignment_strength"]), 4),
            "weight_missingness": round(float(weights["missingness"]), 4),
            "weight_sensor_coverage": round(float(weights["sensor_coverage"]), 4),
            "weight_stability_factor": round(float(weights["stability_factor"]), 4),
        },
    }
