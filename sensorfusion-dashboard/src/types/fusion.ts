export interface DatasetMetric {
  dataset_id: string;
  sampling_rate_hz: number;
  duration_seconds: number;
  start_timestamp?: string | null;
  end_timestamp?: string | null;
}

export interface OverlapWindow {
  start_timestamp?: string | null;
  end_timestamp?: string | null;
  duration_seconds: number;
}

export interface DatasetMetadata {
  datasets: DatasetMetric[];
  overlap_window: OverlapWindow;
}

export interface OffsetCorrection {
  dataset_id: string;
  offset_seconds: number;
}

export interface AlignmentDecisions {
  master_sampling_rate_hz: number;
  offset_corrections: OffsetCorrection[];
  drift_detected: boolean;
  resampling_strategy: Record<string, string>;
  alignment_mode?: "classical" | string;
  requested_sampling_rate_hz?: number | null;
  suggested_sampling_rate_applied?: boolean | null;
}

export interface DataIntegrity {
  missing_modalities: string[];
  missingness_percentage_by_modality: Record<string, number>;
  distribution_divergence_score: number;
}

export interface HQScoreV4Components {
  distribution_similarity: number;
  spectral_similarity: number;
  temporal_alignment_strength: number;
  missingness_penalty: number;
  sensor_coverage: number;
  stability_factor: number;
}

export interface HQScoreV4 {
  overall: number;
  components: HQScoreV4Components;
  advanced_metrics: Record<string, number>;
}

export interface DriftTrendPoint {
  timestamp?: string | null;
  offset_seconds: number;
  correlation_strength: number;
}

export interface DriftAnalysis {
  drift_detected: boolean;
  drift_type: "none" | "minor" | "significant" | string;
  average_window_offset: number;
  dtw_score: number;
  stability_score: number;
  offset_trend: DriftTrendPoint[];
  explanation?: string | null;
}

export interface ConfidenceInfo {
  level: "High" | "Medium" | "Low" | string;
  reason: string;
}

export interface SchemaInferenceInfo {
  method: "rule_based" | "llm" | string;
  confidence: number;
  reasoning_summary?: string | null;
}

export interface TaskInferenceInfo {
  predicted_task: string;
  confidence: number;
  reasoning: string;
  suggested_window_seconds?: number | null;
  suggested_sampling_rate_hz?: number | null;
  hqscore_weight_profile?: string | null;
}

export interface AdaptiveTrendPoint {
  job_index: number;
  hqscore: number;
  moving_avg: number;
}

export interface AdaptiveLayerInfo {
  used: boolean;
  confidence: number;
  model_version: string;
  predicted_sampling_rate_hz?: number | null;
  expected_hqscore?: number | null;
  rule_based_sampling_rate_hz?: number | null;
  applied_sampling_rate_hz?: number | null;
  performance_trend: AdaptiveTrendPoint[];
}

export interface AgenticActionTrace {
  iteration: number;
  action_id: string;
  dataset_id: string;
  action_type: string;
  source: string;
  rationale: string;
  score_before: number;
  score_after: number;
  improvement: number;
  observer_confidence?: number | null;
  executor_steps?: number | null;
}

export interface AgenticLayerInfo {
  enabled: boolean;
  used: boolean;
  policy: string;
  iterations: number;
  initial_quality_score: number;
  final_quality_score: number;
  net_improvement: number;
  confidence: number;
  accepted_actions: AgenticActionTrace[];
  rejected_actions: AgenticActionTrace[];
  stop_reason: string;
  error?: string | null;
}

export interface ResearchPaper {
  title: string;
  year?: number | null;
  citation_count: number;
  source: string;
  url?: string | null;
  abstract_snippet?: string | null;
}

export interface ResearchSuggestion {
  recommended_sampling_rate: number | null;
  confidence: number;
  papers: ResearchPaper[];
  summary: string;
  inferred_task: string;
  detected_modalities: string[];
  query: string;
  window_size_seconds?: string | null;
  resampling_strategy?: string | null;
  common_sensor_combinations: string[];
}

export interface FusionReport {
  dataset_metadata: DatasetMetadata;
  alignment_decisions: AlignmentDecisions;
  data_integrity: DataIntegrity;
  hqscore: number;
  schema_inference?: SchemaInferenceInfo | null;
  task_inference?: TaskInferenceInfo | null;
  adaptive_layer?: AdaptiveLayerInfo | null;
  agentic_layer?: AgenticLayerInfo | null;
  hqscore_v4?: HQScoreV4 | null;
  drift_analysis?: DriftAnalysis | null;
  confidence: ConfidenceInfo;
  summary?: string | null;
}

export interface VisualDataPoint {
  timestamp: string;
  [key: string]: string | number | null;
}

export interface VisualData {
  acc_magnitude_overlay: VisualDataPoint[];
  gyro_magnitude_overlay: VisualDataPoint[];
  drift_offset_trend?: VisualDataPoint[];
}

export interface DatasetStructureReport {
  participants_detected: number;
  files_detected: number;
  grouping_strategy: string;
  schema_inference_confidence: number;
  detected_modalities: string[];
  timestamp_ambiguous: boolean;
  warnings: string[];
}

export interface ParticipantFusionSummary {
  participant_id: string;
  hqscore: number;
  sampling_rate: number;
  datasets_used: number;
}

export interface FuseResponse {
  status?: string;
  warnings?: string[];
  structure_report?: DatasetStructureReport;
  participant_reports?: ParticipantFusionSummary[];
  fusion_report?: FusionReport;
  visual_data?: VisualData;
  research_suggestion?: ResearchSuggestion;
  hqscore?: number;
  confidence?: ConfidenceInfo;
  sampling_rate?: number;
  download?: string;
}

export interface FuseJobCreateResponse {
  job_id: string;
  status: "processing" | string;
}

export interface JobStatusResponse {
  job_id: string;
  status: "processing" | "completed" | "completed_with_warnings" | "failed" | string;
  progress: number;
  result?: FuseResponse;
  error_message?: string | null;
  error?: {
    error_type: string;
    message: string;
    details?: Record<string, unknown>;
  } | null;
}

export interface ResearchSuggestionStatusResponse {
  job_id: string;
  status: string;
  progress: number;
  research_suggestion?: ResearchSuggestion | null;
}
