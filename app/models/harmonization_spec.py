from pydantic import BaseModel
from typing import List, Dict, Any


class TransformationRecord(BaseModel):
    step_id: int
    transformation_type: str
    parameters: Dict[str, Any]


class HarmonizationSpec(BaseModel):
    transformations: List[TransformationRecord]
