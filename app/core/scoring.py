import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from app.core.sensor_roles import classify_sensors


# -----------------------------
# ROLE-AWARE MISSINGNESS
# -----------------------------

def compute_role_aware_missingness(df):

    core_cols, ext_cols = classify_sensors(df.columns)

    if not core_cols:
        return 1.0

    core_missing = 1.0 - df[core_cols].isna().mean().mean()

    if ext_cols:
        ext_missing = 1.0 - df[ext_cols].isna().mean().mean()
    else:
        ext_missing = 1.0

    # Core weighted heavier
    return 0.7 * core_missing + 0.3 * ext_missing


# -----------------------------
# SAMPLING
# -----------------------------

def compute_sampling_consistency_score(df, timestamp_col="timestamp"):

    if timestamp_col not in df.columns:
        return 1.0

    ts = pd.to_datetime(df[timestamp_col], errors="coerce").dropna()

    if len(ts) < 3:
        return 1.0

    diffs = ts.diff().dropna().dt.total_seconds()
    variance = np.var(diffs)

    return float(1.0 / (1.0 + variance))


# -----------------------------
# DISTRIBUTION
# -----------------------------

def compute_distribution_similarity(df):

    numeric_df = df.select_dtypes(include=["number"])

    if numeric_df.empty:
        return 1.0

    similarities = []

    for col in numeric_df.columns:

        series = numeric_df[col].dropna()

        if len(series) < 30:
            continue

        hist1, _ = np.histogram(series, bins=30, density=True)
        hist2, _ = np.histogram(series.sample(frac=1.0), bins=30, density=True)

        hist1 = hist1 + 1e-8
        hist2 = hist2 + 1e-8

        js = jensenshannon(hist1, hist2)
        similarities.append(1 - js)

    if not similarities:
        return 1.0

    return float(np.mean(similarities))


# -----------------------------
# PHYSICS CHECKS
# -----------------------------

def compute_acc_physics_score(df):

    acc_cols = [c for c in df.columns if "acc" in c.lower()]

    if len(acc_cols) < 3:
        return 1.0

    try:
        x, y, z = df[acc_cols[0]], df[acc_cols[1]], df[acc_cols[2]]
        magnitude = np.sqrt(x**2 + y**2 + z**2)
        mean_mag = magnitude.mean()

        if 8.5 <= mean_mag <= 11.5:
            return 1.0
        elif 0.8 <= mean_mag <= 1.2:
            return 0.7
        else:
            return 0.3

    except:
        return 0.5


def compute_gyro_physics_score(df):

    gyro_cols = [c for c in df.columns if "gyro" in c.lower()]

    if len(gyro_cols) < 3:
        return 1.0

    try:
        x, y, z = df[gyro_cols[0]], df[gyro_cols[1]], df[gyro_cols[2]]
        magnitude = np.sqrt(x**2 + y**2 + z**2)
        mean_mag = magnitude.mean()

        if mean_mag < 5:
            return 1.0
        elif mean_mag < 20:
            return 0.7
        else:
            return 0.3

    except:
        return 0.5


# -----------------------------
# FINAL HQ SCORE v4
# -----------------------------

def compute_hq_score(df):

    missingness = compute_role_aware_missingness(df)
    sampling = compute_sampling_consistency_score(df)
    distribution = compute_distribution_similarity(df)
    acc_physics = compute_acc_physics_score(df)
    gyro_physics = compute_gyro_physics_score(df)

    score = (
        0.30 * missingness +
        0.20 * sampling +
        0.20 * distribution +
        0.20 * acc_physics +
        0.10 * gyro_physics
    )

    return round(float(score), 4)
