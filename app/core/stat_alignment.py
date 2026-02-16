import numpy as np
from scipy.stats import entropy


def js_divergence(p, q):

    p = np.asarray(p)
    q = np.asarray(q)

    p = p / (p.sum() + 1e-8)
    q = q / (q.sum() + 1e-8)

    m = 0.5 * (p + q)

    return 0.5 * entropy(p, m) + 0.5 * entropy(q, m)


def compute_distribution_similarity(df, columns):

    scores = []

    for col in columns:
        if col in df.columns:
            data = df[col].dropna()

            if len(data) < 50:
                continue

            hist, _ = np.histogram(data, bins=50, density=True)

            uniform = np.ones_like(hist) / len(hist)

            js = js_divergence(hist + 1e-8, uniform + 1e-8)

            scores.append(1 - js)

    if len(scores) == 0:
        return 1.0

    return float(np.mean(scores))
