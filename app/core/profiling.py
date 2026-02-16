import pandas as pd
import numpy as np
import os
from typing import Optional
from app.models.dataset_profile import DatasetProfile, ColumnStats, TimeStats


def detect_timestamp_column(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        lower = col.lower()
        if "time" in lower or "timestamp" in lower or "date" in lower:
            return col
    return None


def infer_sampling_rate(timestamps: pd.Series) -> Optional[float]:
    if len(timestamps) < 2:
        return None

    diffs = timestamps.diff().dropna().dt.total_seconds()
    if len(diffs) == 0:
        return None

    median_diff = np.median(diffs)

    if median_diff <= 0:
        return None

    return round(1.0 / median_diff, 3)


def validate_time_continuity(timestamps: pd.Series) -> bool:
    if len(timestamps) < 2:
        return True

    diffs = timestamps.diff().dropna().dt.total_seconds()
    median_diff = np.median(diffs)

    tolerance = median_diff * 0.2  # 20% tolerance
    return bool(np.all(np.abs(diffs - median_diff) < tolerance))


def compute_numeric_stats(series: pd.Series):
    if series.dropna().empty:
        return None, None, None, None

    return (
        float(series.mean()),
        float(series.std()),
        float(series.min()),
        float(series.max()),
    )


def profile_dataset(file_path: str) -> DatasetProfile:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    df = pd.read_csv(file_path)

    if df.empty:
        raise ValueError("Dataset is empty.")

    column_stats = {}
    numeric_columns = []

    for col in df.columns:
        dtype = str(df[col].dtype)
        missing_ratio = round(float(df[col].isna().mean()), 4)

        stats_data = {
            "dtype": dtype,
            "missing_ratio": missing_ratio,
        }

        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_columns.append(col)
            mean, std, min_val, max_val = compute_numeric_stats(df[col])
            stats_data.update({
                "mean": mean,
                "std": std,
                "min": min_val,
                "max": max_val,
            })

        column_stats[col] = ColumnStats(**stats_data)

    timestamp_col = detect_timestamp_column(df)
    time_stats = None

    if timestamp_col:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce")
        timestamps = df[timestamp_col].dropna()

        if not timestamps.empty:
            start_time = timestamps.iloc[0]
            end_time = timestamps.iloc[-1]
            duration = (end_time - start_time).total_seconds()

            sampling_rate = infer_sampling_rate(timestamps)
            continuity = validate_time_continuity(timestamps)

            time_stats = TimeStats(
                start_time=str(start_time),
                end_time=str(end_time),
                duration_seconds=duration,
                inferred_sampling_rate_hz=sampling_rate,
                time_continuity_ok=continuity,
            )

    return DatasetProfile(
        dataset_name=os.path.basename(file_path),
        file_path=file_path,
        num_rows=len(df),
        num_columns=len(df.columns),
        columns=list(df.columns),
        numeric_columns=numeric_columns,
        timestamp_column=timestamp_col,
        column_stats=column_stats,
        time_stats=time_stats,
    )
