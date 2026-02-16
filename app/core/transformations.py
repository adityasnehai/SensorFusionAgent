import pandas as pd
from typing import Dict


def rename_columns(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    return df.rename(columns=mapping)


def scale_units(df: pd.DataFrame, column: str, factor: float) -> pd.DataFrame:
    df_copy = df.copy()
    df_copy[column] = df_copy[column] * factor
    return df_copy


def invert_axis(df: pd.DataFrame, column: str) -> pd.DataFrame:
    df_copy = df.copy()
    df_copy[column] = -df_copy[column]
    return df_copy


def smooth_signal(df: pd.DataFrame, column: str, window: int = 5) -> pd.DataFrame:
    df_copy = df.copy()
    if column not in df_copy.columns:
        return df_copy

    window = max(3, int(window))
    if window % 2 == 0:
        window += 1

    series = pd.to_numeric(df_copy[column], errors="coerce")
    if series.notna().sum() < window:
        return df_copy

    # Centered rolling median keeps local shape while suppressing high-frequency spikes.
    smoothed = series.rolling(window=window, center=True, min_periods=1).median()
    df_copy[column] = smoothed
    return df_copy


def resample_timeseries(
    df: pd.DataFrame,
    timestamp_column: str,
    target_hz: float,
) -> pd.DataFrame:

    df_copy = df.copy()

    # 🔥 Robust timestamp parsing
    df_copy[timestamp_column] = pd.to_datetime(
        df_copy[timestamp_column],
        errors="coerce",
        format="mixed"
    )

    df_copy = df_copy.dropna(subset=[timestamp_column])
    df_copy = df_copy.sort_values(timestamp_column)

    df_copy = df_copy.set_index(timestamp_column)

    interval_ms = int(1000 / target_hz)
    rule = f"{interval_ms}ms"   # modern pandas prefers ms not L

    df_resampled = df_copy.resample(rule).mean().interpolate()

    df_resampled = df_resampled.reset_index()

    return df_resampled
