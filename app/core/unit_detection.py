import numpy as np
import pandas as pd


def detect_acc_unit(df: pd.DataFrame):

    acc_cols = [c for c in df.columns if "acc" in c.lower()]

    if len(acc_cols) < 3:
        return None

    try:
        acc_x = df[acc_cols[0]]
        acc_y = df[acc_cols[1]]
        acc_z = df[acc_cols[2]]

        magnitude = np.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
        mean_mag = magnitude.mean()

        # If close to 1 → probably g
        if 0.7 <= mean_mag <= 1.3:
            return "g"

        # If close to 9.8 → already m/s²
        if 8 <= mean_mag <= 11:
            return "ms2"

        return "unknown"

    except:
        return None


def get_scaling_factor(unit_detected: str):
    if unit_detected == "g":
        return 9.81
    return None
