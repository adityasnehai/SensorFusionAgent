import pandas as pd
from app.core.scoring import compute_hq_score


class Observer:

    def evaluate(self, df: pd.DataFrame):
        return compute_hq_score(df)

    def compute_confidence(self, score_before: float, score_after: float) -> float:
        improvement = score_after - score_before

        if improvement <= 0:
            return 0.3

        if improvement < 0.01:
            return 0.6

        if improvement < 0.05:
            return 0.8

        return 0.95
