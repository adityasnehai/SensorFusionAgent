import numpy as np
import pandas as pd


def infer_sampling_rate(df: pd.DataFrame, timestamp_col="timestamp"):

    if timestamp_col not in df.columns:
        return None

    ts = pd.to_datetime(df[timestamp_col], errors="coerce").dropna()

    if len(ts) < 3:
        return None

    diffs = ts.diff().dropna().dt.total_seconds()

    median_diff = np.median(diffs)

    if median_diff <= 0:
        return None

    return round(1.0 / median_diff, 3)
