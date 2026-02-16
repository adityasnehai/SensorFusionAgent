import pandas as pd
from app.llm.semantic import semantic_column_alignment


def align_timestamp_column(df, timestamp_col):
    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce", format="mixed")
    df = df.dropna(subset=[timestamp_col])
    df = df.sort_values(timestamp_col)
    return df


def merge_datasets(df1, df2, timestamp_col="timestamp"):

    df1 = align_timestamp_column(df1, timestamp_col)
    df2 = align_timestamp_column(df2, timestamp_col)

    # 🔥 LLM semantic mapping
    mapping = semantic_column_alignment(df1.columns.tolist(), df2.columns.tolist())

    if mapping:
        df2 = df2.rename(columns=mapping)

    merged = pd.merge_asof(
        df1.sort_values(timestamp_col),
        df2.sort_values(timestamp_col),
        on=timestamp_col,
        direction="nearest",
        tolerance=pd.Timedelta("20ms"),
    )

    return merged
