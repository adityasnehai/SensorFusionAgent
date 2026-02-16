from pydantic import BaseModel
from typing import List, Dict, Any


class DecisionRecord(BaseModel):
    iteration: int
    transformation_type: str
    parameters: Dict[str, Any]
    score_before: float
    score_after: float
    improvement: float
    confidence: float


class ConfidenceSummary(BaseModel):
    final_score: float
    decisions: List[DecisionRecord]
    overall_confidence: float
