from pydantic import BaseModel
from typing import Dict, List, Optional


class ColumnStats(BaseModel):
    dtype: str
    missing_ratio: float
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None


class TimeStats(BaseModel):
    start_time: Optional[str]
    end_time: Optional[str]
    duration_seconds: Optional[float]
    inferred_sampling_rate_hz: Optional[float]
    time_continuity_ok: bool


class DatasetProfile(BaseModel):
    dataset_name: str
    file_path: str
    num_rows: int
    num_columns: int
    columns: List[str]
    numeric_columns: List[str]
    timestamp_column: Optional[str]
    column_stats: Dict[str, ColumnStats]
    time_stats: Optional[TimeStats]
