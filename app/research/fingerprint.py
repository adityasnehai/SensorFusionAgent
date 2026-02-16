from app.core.modality_registry import MODALITY_REGISTRY


def generate_fingerprint(df):

    modalities_present = []

    for modality, config in MODALITY_REGISTRY.items():
        for col in config["columns"]:
            if col in df.columns:
                modalities_present.append(modality)
                break

    sampling_rate = 0

    if "timestamp" in df.columns:
        diffs = df["timestamp"].diff().dt.total_seconds().dropna()
        if len(diffs) > 0:
            median = diffs.median()
            if median > 0:
                sampling_rate = round(1.0 / median, 2)

    return {
        "modalities": modalities_present,
        "sampling_rate": sampling_rate,
        "rows": len(df),
    }
