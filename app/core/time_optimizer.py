import pandas as pd
import numpy as np


def estimate_sampling_rate(df):

    if "timestamp" not in df.columns:
        return 1.0

    diffs = df["timestamp"].diff().dt.total_seconds().dropna()

    if len(diffs) == 0:
        return 1.0

    median_diff = diffs.median()

    if median_diff == 0:
        return 1.0

    return round(1.0 / median_diff, 2)


def compute_acc_magnitude(df):

    if all(col in df.columns for col in ["acc_x", "acc_y", "acc_z"]):
        return np.sqrt(df["acc_x"]**2 + df["acc_y"]**2 + df["acc_z"]**2)

    return None


def estimate_offset(base_df, target_df, max_lag=200):

    base_mag = compute_acc_magnitude(base_df)
    target_mag = compute_acc_magnitude(target_df)

    if base_mag is None or target_mag is None:
        return 0

    base_mag = base_mag.fillna(0).values
    target_mag = target_mag.fillna(0).values

    min_len = min(len(base_mag), len(target_mag))

    if min_len < 50:
        return 0

    base_mag = base_mag[:min_len]
    target_mag = target_mag[:min_len]

    corr = np.correlate(base_mag - base_mag.mean(),
                        target_mag - target_mag.mean(),
                        mode="full")

    lag = corr.argmax() - (len(base_mag) - 1)

    return lag


def build_global_time_grid(datasets, target_rate):

    start_times = []
    end_times = []

    for df in datasets:
        start_times.append(df["timestamp"].min())
        end_times.append(df["timestamp"].max())

    global_start = max(start_times)
    global_end = min(end_times)

    if global_start >= global_end:
        raise ValueError("No overlapping time range across datasets")

    freq_ms = int(1000 / target_rate)

    global_index = pd.date_range(
        start=global_start,
        end=global_end,
        freq=f"{freq_ms}ms"
    )

    return global_index


def resample_to_grid(df, global_index):

    df = df.set_index("timestamp")

    df = df.reindex(global_index)

    df = df.interpolate(method="time")

    df = df.reset_index().rename(columns={"index": "timestamp"})

    return df
