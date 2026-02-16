import numpy as np


def compute_acc_magnitude(df):
    if all(c in df.columns for c in ["acc_x", "acc_y", "acc_z"]):
        return np.sqrt(
            df["acc_x"]**2 +
            df["acc_y"]**2 +
            df["acc_z"]**2
        )
    return None


def estimate_offset(base_df, target_df):

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

    corr = np.correlate(
        base_mag - base_mag.mean(),
        target_mag - target_mag.mean(),
        mode="full"
    )

    lag = corr.argmax() - (len(base_mag) - 1)

    return lag
