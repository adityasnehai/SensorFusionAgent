from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from app.models.research_suggestion import ResearchSuggestion


class DatasetMetric(BaseModel):
    dataset_id: str
    sampling_rate_hz: float
    duration_seconds: float
    start_timestamp: Optional[str] = None
    end_timestamp: Optional[str] = None


class OverlapWindow(BaseModel):
    start_timestamp: Optional[str] = None
    end_timestamp: Optional[str] = None
    duration_seconds: float


class DatasetMetadata(BaseModel):
    datasets: List[DatasetMetric]
    overlap_window: OverlapWindow


class OffsetCorrection(BaseModel):
    dataset_id: str
    offset_seconds: float


class AlignmentDecisions(BaseModel):
    master_sampling_rate_hz: float
    offset_corrections: List[OffsetCorrection]
    drift_detected: bool
    resampling_strategy: Dict[str, str]
    alignment_mode: str = "classical"
    requested_sampling_rate_hz: Optional[float] = None
    suggested_sampling_rate_applied: Optional[bool] = None


class DataIntegrity(BaseModel):
    missing_modalities: List[str]
    missingness_percentage_by_modality: Dict[str, float]
    distribution_divergence_score: float


class ConfidenceInfo(BaseModel):
    level: str
    reason: str


class ErrorInfo(BaseModel):
    error_type: str
    message: str
    details: Dict[str, str | float | int | bool | None] = Field(default_factory=dict)


class SchemaInferenceInfo(BaseModel):
    method: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_summary: Optional[str] = None


class TaskInferenceInfo(BaseModel):
    predicted_task: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    suggested_window_seconds: Optional[float] = None
    suggested_sampling_rate_hz: Optional[float] = None
    hqscore_weight_profile: Optional[str] = None


class AdaptiveTrendPoint(BaseModel):
    job_index: float
    hqscore: float = Field(ge=0.0, le=1.0)
    moving_avg: float = Field(ge=0.0, le=1.0)


class AdaptiveLayerInfo(BaseModel):
    used: bool
    confidence: float = Field(ge=0.0, le=1.0)
    model_version: str
    predicted_sampling_rate_hz: Optional[float] = None
    expected_hqscore: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    rule_based_sampling_rate_hz: Optional[float] = None
    applied_sampling_rate_hz: Optional[float] = None
    performance_trend: List[AdaptiveTrendPoint] = Field(default_factory=list)


class AgenticActionTrace(BaseModel):
    iteration: int
    action_id: str
    dataset_id: str
    action_type: str
    source: str
    rationale: str
    score_before: float = Field(ge=0.0, le=1.0)
    score_after: float = Field(ge=0.0, le=1.0)
    improvement: float
    observer_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    executor_steps: Optional[int] = Field(default=None, ge=0)


class AgenticLayerInfo(BaseModel):
    enabled: bool
    used: bool
    policy: str
    iterations: int = Field(ge=0)
    initial_quality_score: float = Field(ge=0.0, le=1.0)
    final_quality_score: float = Field(ge=0.0, le=1.0)
    net_improvement: float
    confidence: float = Field(ge=0.0, le=1.0)
    accepted_actions: List[AgenticActionTrace] = Field(default_factory=list)
    rejected_actions: List[AgenticActionTrace] = Field(default_factory=list)
    stop_reason: str
    error: Optional[str] = None


class VisualData(BaseModel):
    acc_magnitude_overlay: List[Dict[str, Optional[float | str]]]
    gyro_magnitude_overlay: List[Dict[str, Optional[float | str]]]
    drift_offset_trend: List[Dict[str, Optional[float | str]]] = Field(default_factory=list)


class HQScoreV4Components(BaseModel):
    distribution_similarity: float = Field(ge=0.0, le=1.0)
    spectral_similarity: float = Field(ge=0.0, le=1.0)
    temporal_alignment_strength: float = Field(ge=0.0, le=1.0)
    missingness_penalty: float = Field(ge=0.0, le=1.0)
    sensor_coverage: float = Field(ge=0.0, le=1.0)
    stability_factor: float = Field(ge=0.0, le=1.0)


class HQScoreV4(BaseModel):
    overall: float = Field(ge=0.0, le=1.0)
    components: HQScoreV4Components
    advanced_metrics: Dict[str, float] = Field(default_factory=dict)


class DriftTrendPoint(BaseModel):
    timestamp: Optional[str] = None
    offset_seconds: float
    correlation_strength: float = Field(ge=0.0, le=1.0)


class DriftAnalysis(BaseModel):
    drift_detected: bool
    drift_type: str
    average_window_offset: float
    dtw_score: float = Field(ge=0.0, le=1.0)
    stability_score: float = Field(ge=0.0, le=1.0)
    offset_trend: List[DriftTrendPoint] = Field(default_factory=list)
    explanation: Optional[str] = None


class FusionReport(BaseModel):
    dataset_metadata: DatasetMetadata
    alignment_decisions: AlignmentDecisions
    data_integrity: DataIntegrity
    hqscore: float = Field(ge=0.0, le=1.0)
    schema_inference: Optional[SchemaInferenceInfo] = None
    task_inference: Optional[TaskInferenceInfo] = None
    adaptive_layer: Optional[AdaptiveLayerInfo] = None
    agentic_layer: Optional[AgenticLayerInfo] = None
    hqscore_v4: Optional[HQScoreV4] = None
    drift_analysis: Optional[DriftAnalysis] = None
    confidence: ConfidenceInfo
    warnings: List[str] = Field(default_factory=list)
    summary: Optional[str] = None


class DatasetStructureReport(BaseModel):
    participants_detected: int = Field(ge=0)
    files_detected: int = Field(ge=0)
    grouping_strategy: str
    schema_inference_confidence: float = Field(ge=0.0, le=1.0)
    detected_modalities: List[str]
    timestamp_ambiguous: bool = False
    warnings: List[str] = Field(default_factory=list)


class ParticipantFusionSummary(BaseModel):
    participant_id: str
    hqscore: float = Field(ge=0.0, le=1.0)
    sampling_rate: float
    datasets_used: int = Field(ge=2)


class FuseResponse(BaseModel):
    status: str
    warnings: List[str] = Field(default_factory=list)
    structure_report: Optional[DatasetStructureReport] = None
    participant_reports: List[ParticipantFusionSummary] = Field(default_factory=list)
    fusion_report: FusionReport
    visual_data: VisualData
    research_suggestion: Optional[ResearchSuggestion] = None
    hqscore: float = Field(ge=0.0, le=1.0)
    confidence: ConfidenceInfo
    sampling_rate: float
    download: str


class FuseJobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    result: Optional[FuseResponse] = None
    error_message: Optional[str] = None
    error: Optional[ErrorInfo] = None
