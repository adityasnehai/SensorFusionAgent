import pandas as pd
import numpy as np


# -------------------------------------------------
# Resampling Operation
# -------------------------------------------------

def resample_dataframe(df, target_rate):

    if "timestamp" not in df.columns:
        return df

    df = df.sort_values("timestamp")

    freq_ms = int(1000 / target_rate)

    new_index = pd.date_range(
        start=df["timestamp"].min(),
        end=df["timestamp"].max(),
        freq=f"{freq_ms}ms"
    )

    df = df.set_index("timestamp")
    df = df.reindex(new_index)
    df = df.interpolate(method="time")

    df = df.reset_index().rename(columns={"index": "timestamp"})

    return df


# -------------------------------------------------
# Low-pass Filter (Simple Rolling Mean)
# -------------------------------------------------

def low_pass_filter(df, window_size=5):

    numeric_cols = df.select_dtypes(include=np.number).columns

    for col in numeric_cols:
        df[col] = df[col].rolling(window=window_size, min_periods=1).mean()

    return df


# -------------------------------------------------
# Apply Suggested Operation
# -------------------------------------------------

def apply_operation(df, suggestion):

    if not suggestion:
        return df

    if "recommended_sampling_rate" in suggestion:
        rate = suggestion["recommended_sampling_rate"]
        df = resample_dataframe(df, rate)

    if "filtering" in suggestion:
        if "low-pass" in suggestion["filtering"].lower():
            df = low_pass_filter(df)

    return df
