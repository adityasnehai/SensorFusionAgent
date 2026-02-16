import numpy as np
from app.core.modality_registry import MODALITY_REGISTRY


def modality_missingness(df, columns):

    available = [c for c in columns if c in df.columns]

    if not available:
        return 1.0

    missing = df[available].isna().mean().mean()

    return 1 - float(missing)


def temporal_consistency(df):

    if "timestamp" not in df.columns:
        return 0.5

    diffs = df["timestamp"].diff().dt.total_seconds().dropna()

    if len(diffs) == 0:
        return 0.5

    std = diffs.std()

    return 1 / (1 + std)


def compute_hqscore_v3(df):

    modality_scores = []

    for modality, config in MODALITY_REGISTRY.items():

        score = modality_missingness(df, config["columns"])
        weighted = score * config["weight"]

        modality_scores.append(weighted)

    temporal_score = temporal_consistency(df)

    final_score = sum(modality_scores) * 0.8 + temporal_score * 0.2

    return round(float(final_score), 4)
