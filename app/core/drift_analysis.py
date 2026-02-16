from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _resample_to_points(signal: np.ndarray, max_points: int) -> np.ndarray:
    if len(signal) <= max_points:
        return signal.astype(float)

    x_old = np.linspace(0.0, 1.0, len(signal))
    x_new = np.linspace(0.0, 1.0, max_points)
    return np.interp(x_new, x_old, signal.astype(float))


def _acc_magnitude(df: pd.DataFrame) -> tuple[np.ndarray, pd.Series]:
    if not all(col in df.columns for col in ("acc_x", "acc_y", "acc_z")):
        return np.array([], dtype=float), pd.Series([], dtype="datetime64[ns]")

    numeric = df[["acc_x", "acc_y", "acc_z"]].apply(pd.to_numeric, errors="coerce")
    magnitude = np.sqrt((numeric ** 2).sum(axis=1))
    valid = magnitude.notna()
    if valid.sum() < 8:
        return np.array([], dtype=float), pd.Series([], dtype="datetime64[ns]")

    return magnitude[valid].to_numpy(dtype=float), df.loc[valid, "timestamp"]


def _normalized_xcorr(x: np.ndarray, y: np.ndarray) -> tuple[int, float]:
    if len(x) != len(y) or len(x) < 8:
        return 0, 0.0

    x_centered = x - np.mean(x)
    y_centered = y - np.mean(y)
    denom = float(np.linalg.norm(x_centered) * np.linalg.norm(y_centered)) + 1e-9
    if denom <= 1e-9:
        return 0, 0.0

    corr = np.correlate(x_centered, y_centered, mode="full")
    idx = int(np.argmax(np.abs(corr)))
    lag = idx - (len(x_centered) - 1)
    peak = float(np.abs(corr[idx]) / denom)
    return lag, _clip01(peak)


def _windowed_offsets(
    base_signal: np.ndarray,
    target_signal: np.ndarray,
    base_timestamps: pd.Series,
    sampling_rate_hz: float,
    window_seconds: float = 5.0,
) -> List[dict]:
    min_len = min(len(base_signal), len(target_signal))
    if min_len < 10 or sampling_rate_hz <= 0:
        return []

    x = base_signal[:min_len]
    y = target_signal[:min_len]
    ts = base_timestamps.iloc[:min_len]

    window_size = max(10, int(round(window_seconds * sampling_rate_hz)))
    if window_size >= min_len:
        lag, peak = _normalized_xcorr(x, y)
        midpoint = min_len // 2
        return [
            {
                "timestamp": ts.iloc[midpoint].isoformat() if midpoint < len(ts) else None,
                "offset_seconds": float(round(float(lag) / float(sampling_rate_hz), 6)),
                "correlation_strength": float(round(float(peak), 6)),
            }
        ]

    step = max(5, window_size // 2)
    trend_points: List[dict] = []

    for start in range(0, min_len - window_size + 1, step):
        end = start + window_size
        lag, peak = _normalized_xcorr(x[start:end], y[start:end])
        midpoint = start + (window_size // 2)

        trend_points.append(
            {
                "timestamp": ts.iloc[midpoint].isoformat() if midpoint < len(ts) else None,
                "offset_seconds": float(round(float(lag) / float(sampling_rate_hz), 6)),
                "correlation_strength": float(round(float(peak), 6)),
            }
        )

    return trend_points


def _dtw_distance(x: np.ndarray, y: np.ndarray) -> float:
    n = len(x)
    m = len(y)
    if n == 0 or m == 0:
        return 0.0

    prev = np.full(m + 1, np.inf)
    curr = np.full(m + 1, np.inf)
    prev[0] = 0.0

    for i in range(1, n + 1):
        curr[0] = np.inf
        xi = x[i - 1]
        for j in range(1, m + 1):
            cost = abs(xi - y[j - 1])
            curr[j] = cost + min(curr[j - 1], prev[j], prev[j - 1])
        prev, curr = curr, prev

    return float(prev[m])


def _normalize_dtw(raw_dtw: float, x: np.ndarray, y: np.ndarray) -> float:
    scale = (len(x) + len(y)) * (float(np.std(x)) + float(np.std(y)) + 1e-6)
    if scale <= 1e-9:
        return 0.0
    return _clip01(raw_dtw / scale)


def analyze_drift(
    resampled: List[pd.DataFrame],
    sampling_rate_hz: float,
    max_points: int = 2000,
) -> dict:
    if len(resampled) < 2:
        return {
            "drift_detected": False,
            "drift_type": "none",
            "average_window_offset": 0.0,
            "dtw_score": 0.0,
            "stability_score": 1.0,
            "offset_trend": [],
            "explanation": "Single dataset; drift analysis skipped.",
        }

    base_signal, base_ts = _acc_magnitude(resampled[0])
    if len(base_signal) == 0:
        return {
            "drift_detected": False,
            "drift_type": "none",
            "average_window_offset": 0.0,
            "dtw_score": 0.0,
            "stability_score": 0.6,
            "offset_trend": [],
            "explanation": "Accelerometer magnitude unavailable for drift analysis.",
        }

    base_signal = _resample_to_points(base_signal, max_points)

    all_offsets: List[float] = []
    all_peaks: List[float] = []
    trend_reference: List[dict] = []
    dtw_scores: List[float] = []

    for i in range(1, len(resampled)):
        target_signal, _ = _acc_magnitude(resampled[i])
        if len(target_signal) == 0:
            continue

        target_signal = _resample_to_points(target_signal, max_points)
        min_len = min(len(base_signal), len(target_signal), len(base_ts))
        if min_len < 12:
            continue

        x = base_signal[:min_len]
        y = target_signal[:min_len]
        timestamps = base_ts.iloc[:min_len]

        trend = _windowed_offsets(x, y, timestamps, sampling_rate_hz, window_seconds=5.0)
        if trend and not trend_reference:
            trend_reference = trend

        offsets = [float(item["offset_seconds"]) for item in trend]
        peaks = [float(item["correlation_strength"]) for item in trend]

        all_offsets.extend(offsets)
        all_peaks.extend(peaks)

        dtw_raw = _dtw_distance(_resample_to_points(x, 600), _resample_to_points(y, 600))
        dtw_scores.append(_normalize_dtw(dtw_raw, x, y))

    if not all_offsets:
        return {
            "drift_detected": False,
            "drift_type": "none",
            "average_window_offset": 0.0,
            "dtw_score": 0.0,
            "stability_score": 0.7,
            "offset_trend": trend_reference,
            "explanation": "Insufficient overlap for sliding-window drift analysis.",
        }

    avg_abs_offset = float(np.mean(np.abs(np.array(all_offsets, dtype=float))))
    avg_peak = float(np.mean(np.array(all_peaks, dtype=float))) if all_peaks else 0.0

    slope = 0.0
    if len(all_offsets) >= 2:
        x_idx = np.arange(len(all_offsets), dtype=float)
        slope = float(np.polyfit(x_idx, np.array(all_offsets, dtype=float), 1)[0])

    dtw_score = float(np.mean(np.array(dtw_scores, dtype=float))) if dtw_scores else 0.0

    if avg_abs_offset < 0.01 and abs(slope) < 0.0005 and dtw_score < 0.12:
        drift_type = "none"
    elif avg_abs_offset < 0.05 and abs(slope) < 0.002 and dtw_score < 0.35:
        drift_type = "minor"
    else:
        drift_type = "significant"

    drift_detected = drift_type != "none"

    instability = (
        0.5 * min(1.0, avg_abs_offset / 0.1)
        + 0.3 * min(1.0, abs(slope) / 0.005)
        + 0.2 * dtw_score
    )
    stability_score = _clip01(1.0 - instability)

    explanation = (
        f"Windowed offset mean={avg_abs_offset:.4f}s, slope={slope:.6f}, "
        f"mean peak correlation={avg_peak:.3f}, normalized DTW={dtw_score:.3f}."
    )

    return {
        "drift_detected": bool(drift_detected),
        "drift_type": drift_type,
        "average_window_offset": round(avg_abs_offset, 6),
        "dtw_score": round(dtw_score, 6),
        "stability_score": round(stability_score, 6),
        "offset_trend": trend_reference,
        "explanation": explanation,
    }
