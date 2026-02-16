import numpy as np


def compute_hqscore_v3(df):

    if len(df) == 0:
        return 0.0

    score = 0.0

    # -------------------------------------------------
    # Missingness Score
    # -------------------------------------------------

    missing_ratio = df.isna().mean().mean()
    missing_score = max(0, 1 - missing_ratio)

    # -------------------------------------------------
    # Variance Score (basic sanity)
    # -------------------------------------------------

    numeric = df.select_dtypes(include=np.number)

    if len(numeric.columns) > 0:
        variance = numeric.var().mean()
        variance_score = min(1.0, variance / 100)
    else:
        variance_score = 0.5

    # -------------------------------------------------
    # Final Weighted Score
    # -------------------------------------------------

    score = (
        0.6 * missing_score +
        0.4 * variance_score
    )

    return round(float(score), 4)
