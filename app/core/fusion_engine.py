import os
import uuid
import pandas as pd
from app.agent.loop import HarmonizationLoop
from app.research.suggestion_engine import generate_suggestions
from app.core.operations import apply_operation
from app.core.validation import validate_and_compare


class FusionEngine:

    def __init__(self):
        self.loop = HarmonizationLoop()

    # ---------------------------------------------
    # Fuse multiple datasets
    # ---------------------------------------------

    def fuse(
        self,
        dataframes,
        progress_callback=None,
        target_sampling_rate=None,
        schema_inference=None,
        task_inference=None,
        alignment_mode="classical",
        timeout_seconds=None,
    ):

        fused_df, score, rate, fusion_report, confidence, visual_data = self.loop.run(
            dataframes,
            progress_callback=progress_callback,
            target_sampling_rate=target_sampling_rate,
            schema_inference=schema_inference,
            task_inference=task_inference,
            alignment_mode=alignment_mode,
            timeout_seconds=timeout_seconds,
        )

        return {
            "fused_df": fused_df,
            "score": score,
            "rate": rate,
            "fusion_report": fusion_report,
            "confidence": confidence,
            "visual_data": visual_data,
        }

    # ---------------------------------------------
    # Suggest operations
    # ---------------------------------------------

    def suggest(self, df):

        suggestions = generate_suggestions(df)

        return suggestions

    # ---------------------------------------------
    # Apply suggestion safely
    # ---------------------------------------------

    def apply(self, df, suggestion):

        modified_df = apply_operation(df.copy(), suggestion)

        validation = validate_and_compare(df, modified_df)

        if validation["accepted"]:
            return modified_df, validation
        else:
            return df, validation
