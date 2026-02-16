import pandas as pd
from typing import Dict, Any
from app.core import transformations


class TransformationExecutor:

    def __init__(self):
        self.history = []
        self.step_counter = 0

    def apply(self, df: pd.DataFrame, transformation_type: str, parameters: Dict[str, Any]):

        original_df = df.copy()

        if transformation_type == "rename":
            df = transformations.rename_columns(df, parameters["mapping"])

        elif transformation_type == "scale":
            df = transformations.scale_units(df, parameters["column"], parameters["factor"])

        elif transformation_type == "invert":
            df = transformations.invert_axis(df, parameters["column"])

        elif transformation_type == "smooth":
            df = transformations.smooth_signal(
                df,
                parameters["column"],
                parameters.get("window", 5),
            )

        elif transformation_type == "resample":
            df = transformations.resample_timeseries(
                df,
                parameters["timestamp_column"],
                parameters["target_hz"],
            )

        else:
            raise ValueError(f"Unknown transformation type: {transformation_type}")

        self.step_counter += 1

        self.history.append({
            "step_id": self.step_counter,
            "type": transformation_type,
            "parameters": parameters,
        })

        return df, original_df  # return new + backup

    def rollback(self, backup_df: pd.DataFrame):
        return backup_df
