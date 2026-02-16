import os
import shutil
import json
import uuid
import logging
import pandas as pd
import numpy as np
from statistics import mean
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from app.core.fusion_engine import FusionEngine
from app.core.continual_learning import ContinualLearningManager
from app.models.fusion_report import FuseJobCreateResponse, FuseResponse, JobStatusResponse
from app.models.research_suggestion import ResearchSuggestionStatusResponse
from app.core.database import SessionLocal, Job, init_db
from app.core.exceptions import FusionPipelineError, build_error_payload
from app.ingestion.structure_intelligence import build_fusion_inputs
from app.research.research_suggestion_engine import generate_research_suggestion


app = FastAPI(title="SensorFusionAgent v1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "data/uploads"
OUTPUT_DIR = "outputs"
LOG_DIR = "logs"
FUSION_JOB_TIMEOUT_SECONDS = float(os.getenv("FUSION_JOB_TIMEOUT_SECONDS", "300"))

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
init_db()

fusion_engine = FusionEngine()
continual_learning_manager = ContinualLearningManager()
logger = logging.getLogger("sensorfusion.api")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _file_handler = logging.FileHandler(os.path.join(LOG_DIR, "backend_errors.log"))
    _file_handler.setLevel(logging.ERROR)
    _file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(_file_handler)
    logger.propagate = False


@app.middleware("http")
async def centralized_error_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except HTTPException:
        raise
    except FusionPipelineError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
    except Exception:
        logger.exception("Unhandled middleware exception path=%s", request.url.path)
        payload = build_error_payload(
            error_type="internal_error",
            message="Internal server error.",
            details={},
        )
        return JSONResponse(status_code=500, content=payload)


@app.exception_handler(FusionPipelineError)
async def fusion_pipeline_error_handler(_: Request, exc: FusionPipelineError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    payload = build_error_payload(
        error_type="http_error",
        message=detail,
        details={"status_code": exc.status_code},
    )
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("Unhandled API error")
    payload = build_error_payload(
        error_type="internal_error",
        message="Internal server error.",
        details={},
    )
    return JSONResponse(status_code=500, content=payload)


# ---------------------------------------------------------
# FUSE ENDPOINT
# ---------------------------------------------------------

def _update_job_state(
    session,
    job_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    result: dict | None = None,
    error_message: str | None = None,
    error_payload: dict | None = None,
    research_suggestion: dict | None = None,
    alignment_mode: str | None = None,
    completed_at: datetime | None = None,
    output_path: str | None = None,
):
    job = session.query(Job).filter(Job.id == job_id).first()
    if not job:
        return

    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = max(0, min(100, int(progress)))
    if result is not None:
        job.result_json = json.dumps(result)
    if error_message is not None:
        job.error_message = error_message
    if error_payload is not None:
        job.error_message = json.dumps(error_payload)
    if research_suggestion is not None:
        job.research_suggestion_json = json.dumps(research_suggestion)
    if alignment_mode is not None:
        job.alignment_mode = alignment_mode
    if completed_at is not None:
        job.completed_at = completed_at
    if output_path is not None:
        job.output_path = output_path

    session.commit()


def _create_job_record(job_id: str, alignment_mode: str | None = None):
    session = SessionLocal()
    try:
        job = Job(
            id=job_id,
            status="processing",
            progress=0,
            research_suggestion_json=None,
            result_json=None,
            learning_metadata_json=None,
            error_message=None,
            alignment_mode=alignment_mode,
            created_at=datetime.utcnow(),
            completed_at=None,
        )
        session.add(job)
        session.commit()
    finally:
        session.close()


def _sanitize_relative_upload_path(filename: str) -> str:
    normalized = os.path.normpath(filename or "").replace("\\", "/").lstrip("/")
    if not normalized or normalized in {".", ".."}:
        return "dataset.csv"
    if normalized.startswith("../") or "/../" in normalized:
        return os.path.basename(normalized)
    return normalized


def _save_slot_uploads(
    slot_dir: str,
    uploads: list[UploadFile],
):
    os.makedirs(slot_dir, exist_ok=True)

    for index, upload in enumerate(uploads, start=1):
        safe_name = _sanitize_relative_upload_path(upload.filename or f"dataset_{index}.csv")
        path = os.path.realpath(os.path.join(slot_dir, safe_name))
        slot_root = os.path.realpath(slot_dir)
        if not (path == slot_root or path.startswith(slot_root + os.sep)):
            path = os.path.join(slot_dir, f"dataset_{index}.csv")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)


def _normalize_slot_uploads(
    single_upload: UploadFile | None,
    multi_uploads: list[UploadFile] | None,
) -> list[UploadFile]:
    normalized: list[UploadFile] = []
    if single_upload is not None:
        normalized.append(single_upload)
    if multi_uploads:
        normalized.extend(multi_uploads)
    return normalized


def _normalize_alignment_mode(value: str | None) -> str:
    # Transformer alignment is removed; keep parameter for backward-compatible requests.
    return "classical"


def _estimate_sampling_rate(df: pd.DataFrame) -> float:
    if "timestamp" not in df.columns:
        return 0.0
    ts = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed")
    diffs = ts.diff().dt.total_seconds().dropna()
    if len(diffs) == 0:
        return 0.0
    median = diffs.median()
    if median <= 0:
        return 0.0
    return float(1.0 / median)


def _duration_seconds(df: pd.DataFrame) -> float:
    if "timestamp" not in df.columns or len(df) < 2:
        return 0.0
    ts = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed").dropna()
    if ts.empty:
        return 0.0
    return float(max(0.0, (ts.max() - ts.min()).total_seconds()))


def _collect_context_sampling_rates(participant_inputs: dict[str, list[pd.DataFrame]]) -> list[float]:
    rates: list[float] = []
    for frames in participant_inputs.values():
        for frame in frames:
            rate = _estimate_sampling_rate(frame)
            if rate > 0:
                rates.append(rate)
    return rates


def _collect_context_durations(participant_inputs: dict[str, list[pd.DataFrame]]) -> list[float]:
    durations: list[float] = []
    for frames in participant_inputs.values():
        for frame in frames:
            duration = _duration_seconds(frame)
            if duration > 0:
                durations.append(duration)
    return durations


def _build_learning_metadata(
    *,
    structure_report: dict,
    fusion_report: dict,
    hqscore: float,
    requested_sampling_rate: float | None,
    research_suggestion_accepted: bool,
    adaptive_layer: dict | None,
) -> dict:
    dataset_metadata = fusion_report.get("dataset_metadata") or {}
    alignment_decisions = fusion_report.get("alignment_decisions") or {}
    drift_analysis = fusion_report.get("drift_analysis") or {}
    task_inference = fusion_report.get("task_inference") or {}
    agentic_layer = fusion_report.get("agentic_layer") or {}

    duration_candidates = [
        float(item.get("duration_seconds", 0.0))
        for item in dataset_metadata.get("datasets", [])
        if isinstance(item, dict) and float(item.get("duration_seconds", 0.0)) > 0
    ]

    return {
        "modalities": list(structure_report.get("detected_modalities", [])),
        "sampling_rates_hz": [
            float(item.get("sampling_rate_hz", 0.0))
            for item in dataset_metadata.get("datasets", [])
            if isinstance(item, dict) and float(item.get("sampling_rate_hz", 0.0)) > 0
        ],
        "duration_seconds": float(np.mean(duration_candidates)) if duration_candidates else 0.0,
        "task_type": str(task_inference.get("predicted_task", "Unknown")),
        "chosen_master_rate_hz": float(alignment_decisions.get("master_sampling_rate_hz", 0.0)),
        "offset_applied_seconds": [
            float(item.get("offset_seconds", 0.0))
            for item in alignment_decisions.get("offset_corrections", [])
            if isinstance(item, dict)
        ],
        "hqscore": float(hqscore),
        "drift_classification": str(
            drift_analysis.get("drift_type", "none")
        ),
        "user_override_flag": requested_sampling_rate is not None,
        "research_suggestion_accepted": bool(research_suggestion_accepted),
        "adaptive_used": bool((adaptive_layer or {}).get("used", False)),
        "adaptive_confidence": float((adaptive_layer or {}).get("confidence", 0.0)),
        "agentic_enabled": bool(agentic_layer.get("enabled", False)),
        "agentic_used": bool(agentic_layer.get("used", False)),
        "agentic_iterations": int(agentic_layer.get("iterations", 0) or 0),
        "agentic_improvement": float(agentic_layer.get("net_improvement", 0.0) or 0.0),
        "dataset_structure": {
            "participants_detected": int(structure_report.get("participants_detected", 0)),
            "files_detected": int(structure_report.get("files_detected", 0)),
            "grouping_strategy": str(structure_report.get("grouping_strategy", "unknown")),
        },
        "recorded_at": datetime.utcnow().isoformat(),
    }


def _confidence_level_from_score(score: float) -> str:
    if score >= 0.8:
        return "High"
    if score >= 0.55:
        return "Medium"
    return "Low"


def _aggregate_participant_results(
    participant_results: list[dict],
    intelligence_context: dict | None = None,
    adaptive_layer: dict | None = None,
):
    scores = [float(item["result"]["score"]) for item in participant_results]
    rates = [float(item["result"]["rate"]) for item in participant_results]

    fused_frames = []
    participant_reports = []
    aggregated_warnings: list[str] = []

    for item in participant_results:
        participant_id = item["participant_id"]
        datasets_used = item["datasets_used"]
        result = item["result"]
        fused_df = result["fused_df"].copy()
        fused_df["participant_id"] = participant_id
        fused_frames.append(fused_df)

        participant_reports.append(
            {
                "participant_id": participant_id,
                "hqscore": round(float(result["score"]), 4),
                "sampling_rate": round(float(result["rate"]), 4),
                "datasets_used": datasets_used,
            }
        )
        for warning in (result.get("fusion_report", {}).get("warnings") or []):
            if isinstance(warning, str):
                aggregated_warnings.append(warning)

    merged_output = pd.concat(fused_frames, ignore_index=True).sort_values(
        ["participant_id", "timestamp"]
    )

    aggregate_score = float(mean(scores))
    aggregate_rate = float(mean(rates))

    reference_result = participant_results[0]["result"]
    fusion_report = reference_result["fusion_report"].copy()
    confidence = {
        "level": _confidence_level_from_score(aggregate_score),
        "reason": (
            f"Aggregated across {len(participant_results)} participants. "
            f"Mean HQScore={aggregate_score:.3f}."
        ),
    }

    fusion_report["hqscore"] = round(aggregate_score, 4)
    fusion_report["confidence"] = confidence
    fusion_report["summary"] = (
        f"Harmonized {len(participant_results)} participants. "
        f"Mean HQScore {aggregate_score:.3f} at {aggregate_rate:.2f} Hz."
    )
    if isinstance(intelligence_context, dict):
        schema_inference = intelligence_context.get("schema_inference")
        task_inference = intelligence_context.get("task_inference")
        if isinstance(schema_inference, dict):
            fusion_report["schema_inference"] = schema_inference
        if isinstance(task_inference, dict):
            fusion_report["task_inference"] = task_inference
    if isinstance(adaptive_layer, dict):
        fusion_report["adaptive_layer"] = adaptive_layer

    participant_agentic_pairs = [
        (
            item,
            item["result"].get("fusion_report", {}).get("agentic_layer"),
        )
        for item in participant_results
        if item["result"].get("fusion_report", {}).get("agentic_layer")
    ]
    agentic_payloads = [payload for _, payload in participant_agentic_pairs]
    if agentic_payloads:
        accepted_actions: list[dict] = []
        rejected_actions: list[dict] = []
        for participant_item, payload in participant_agentic_pairs:
            participant_id = participant_item.get("participant_id", "participant")
            for action in payload.get("accepted_actions", []) or []:
                if isinstance(action, dict):
                    enriched = action.copy()
                    enriched["dataset_id"] = f"{participant_id}:{enriched.get('dataset_id', 'dataset')}"
                    accepted_actions.append(enriched)
            for action in payload.get("rejected_actions", []) or []:
                if isinstance(action, dict):
                    enriched = action.copy()
                    enriched["dataset_id"] = f"{participant_id}:{enriched.get('dataset_id', 'dataset')}"
                    rejected_actions.append(enriched)

        enabled_any = any(bool(payload.get("enabled", False)) for payload in agentic_payloads)
        used_any = any(bool(payload.get("used", False)) for payload in agentic_payloads)
        avg_initial = float(mean(float(payload.get("initial_quality_score", 0.0)) for payload in agentic_payloads))
        avg_final = float(mean(float(payload.get("final_quality_score", 0.0)) for payload in agentic_payloads))
        avg_confidence = float(mean(float(payload.get("confidence", 0.0)) for payload in agentic_payloads))
        total_iterations = int(sum(int(payload.get("iterations", 0) or 0) for payload in agentic_payloads))

        fusion_report["agentic_layer"] = {
            "enabled": enabled_any,
            "used": used_any,
            "policy": str(agentic_payloads[0].get("policy", "greedy_safe_search_v1")),
            "iterations": total_iterations,
            "initial_quality_score": round(avg_initial, 4),
            "final_quality_score": round(avg_final, 4),
            "net_improvement": round(avg_final - avg_initial, 4),
            "confidence": round(avg_confidence, 4),
            "accepted_actions": accepted_actions[:25],
            "rejected_actions": rejected_actions[:25],
            "stop_reason": f"aggregated_{len(agentic_payloads)}_participants",
        }

    hqscore_v4_payloads = [
        item["result"].get("fusion_report", {}).get("hqscore_v4")
        for item in participant_results
        if item["result"].get("fusion_report", {}).get("hqscore_v4")
    ]
    if hqscore_v4_payloads:
        component_keys = set()
        for payload in hqscore_v4_payloads:
            component_keys.update((payload.get("components") or {}).keys())

        averaged_components = {
            key: round(
                float(
                    mean(
                        float((payload.get("components") or {}).get(key, 0.0))
                        for payload in hqscore_v4_payloads
                    )
                ),
                4,
            )
            for key in sorted(component_keys)
        }

        metric_keys = set()
        for payload in hqscore_v4_payloads:
            metric_keys.update((payload.get("advanced_metrics") or {}).keys())
        averaged_metrics = {
            key: round(
                float(
                    mean(
                        float((payload.get("advanced_metrics") or {}).get(key, 0.0))
                        for payload in hqscore_v4_payloads
                    )
                ),
                6,
            )
            for key in sorted(metric_keys)
        }

        fusion_report["hqscore_v4"] = {
            "overall": round(aggregate_score, 4),
            "components": averaged_components,
            "advanced_metrics": averaged_metrics,
        }

    drift_payloads = [
        item["result"].get("fusion_report", {}).get("drift_analysis")
        for item in participant_results
        if item["result"].get("fusion_report", {}).get("drift_analysis")
    ]
    if drift_payloads:
        severity_rank = {"none": 0, "minor": 1, "significant": 2}
        worst = max(
            drift_payloads,
            key=lambda payload: severity_rank.get(str(payload.get("drift_type", "none")), 0),
        )

        fusion_report["drift_analysis"] = {
            "drift_detected": any(bool(payload.get("drift_detected")) for payload in drift_payloads),
            "drift_type": worst.get("drift_type", "none"),
            "average_window_offset": round(
                float(mean(float(payload.get("average_window_offset", 0.0)) for payload in drift_payloads)),
                6,
            ),
            "dtw_score": round(
                float(mean(float(payload.get("dtw_score", 0.0)) for payload in drift_payloads)),
                6,
            ),
            "stability_score": round(
                float(mean(float(payload.get("stability_score", 0.0)) for payload in drift_payloads)),
                6,
            ),
            "offset_trend": worst.get("offset_trend", []),
            "explanation": (
                f"Aggregated drift across {len(drift_payloads)} participants; "
                f"worst classification={worst.get('drift_type', 'none')}."
            ),
        }

    visual_data = reference_result["visual_data"]
    if isinstance(fusion_report.get("drift_analysis"), dict):
        visual_data["drift_offset_trend"] = fusion_report["drift_analysis"].get("offset_trend", [])
    if aggregated_warnings:
        fusion_report["warnings"] = list(dict.fromkeys(aggregated_warnings))

    return {
        "fused_df": merged_output,
        "score": aggregate_score,
        "rate": aggregate_rate,
        "fusion_report": fusion_report,
        "confidence": confidence,
        "visual_data": visual_data,
        "participant_reports": participant_reports,
        "warnings": list(dict.fromkeys(aggregated_warnings)),
    }


def _process_fusion_job(
    job_id: str,
    slot_dirs: list[tuple[str, str]],
    requested_sampling_rate: float | None = None,
    preset_research_suggestion: dict | None = None,
    alignment_mode: str | None = None,
    research_suggestion_accepted: bool = False,
):
    session = SessionLocal()

    try:
        resolved_alignment_mode = _normalize_alignment_mode(alignment_mode)
        _update_job_state(session, job_id, status="processing", progress=10)
        participant_inputs, research_frames, structure_report, intelligence_context = build_fusion_inputs(slot_dirs)
        _update_job_state(session, job_id, alignment_mode=resolved_alignment_mode)
        _update_job_state(session, job_id, status="processing", progress=20)

        if not participant_inputs:
            raise FusionPipelineError(
                error_type="insufficient_datasets",
                message="At least two valid datasets are required for fusion.",
                details={},
            )

        context_sampling_rates = _collect_context_sampling_rates(participant_inputs)
        context_durations = _collect_context_durations(participant_inputs)
        adaptive_context = {
            "modalities": structure_report.get("detected_modalities", []),
            "sampling_rates_hz": context_sampling_rates,
            "duration_seconds": float(np.mean(context_durations)) if context_durations else 0.0,
            "task_type": (
                (intelligence_context.get("task_inference") or {}).get("predicted_task", "Unknown")
                if isinstance(intelligence_context, dict)
                else "Unknown"
            ),
            "drift_flag": False,
            "user_override_flag": requested_sampling_rate is not None,
        }
        adaptive_layer = continual_learning_manager.recommend(session, adaptive_context)

        research_suggestion = preset_research_suggestion or generate_research_suggestion(
            research_frames,
            task_context=intelligence_context.get("task_inference") if isinstance(intelligence_context, dict) else None,
        )
        _update_job_state(
            session,
            job_id,
            status="processing",
            progress=30,
            research_suggestion=research_suggestion,
        )

        participant_results = []
        participant_ids = sorted(participant_inputs.keys())
        total_participants = len(participant_ids)

        adaptive_target_sampling_rate = None
        if requested_sampling_rate is None and adaptive_layer.get("used"):
            adaptive_target_sampling_rate = adaptive_layer.get("predicted_sampling_rate_hz")
            if adaptive_target_sampling_rate is not None:
                adaptive_target_sampling_rate = float(adaptive_target_sampling_rate)

        effective_target_sampling_rate = (
            float(requested_sampling_rate)
            if requested_sampling_rate is not None
            else adaptive_target_sampling_rate
        )

        for index, participant_id in enumerate(participant_ids, start=1):
            datasets = participant_inputs[participant_id]
            result = fusion_engine.fuse(
                datasets,
                progress_callback=None,
                target_sampling_rate=effective_target_sampling_rate,
                schema_inference=intelligence_context.get("schema_inference") if isinstance(intelligence_context, dict) else None,
                task_inference=intelligence_context.get("task_inference") if isinstance(intelligence_context, dict) else None,
                alignment_mode=resolved_alignment_mode,
                timeout_seconds=FUSION_JOB_TIMEOUT_SECONDS,
            )
            result["fusion_report"]["adaptive_layer"] = {
                "used": bool(adaptive_layer.get("used") and requested_sampling_rate is None),
                "confidence": round(float(adaptive_layer.get("confidence", 0.0)), 4),
                "model_version": str(adaptive_layer.get("model_version", "untrained")),
                "predicted_sampling_rate_hz": adaptive_layer.get("predicted_sampling_rate_hz"),
                "expected_hqscore": adaptive_layer.get("expected_hqscore"),
                "rule_based_sampling_rate_hz": float(min(context_sampling_rates)) if context_sampling_rates else None,
                "applied_sampling_rate_hz": float(result.get("rate", 0.0)),
                "performance_trend": adaptive_layer.get("performance_trend", []),
            }
            participant_results.append(
                {
                    "participant_id": participant_id,
                    "datasets_used": len(datasets),
                    "result": result,
                }
            )

            progress = 30 + int((index / max(1, total_participants)) * 60)
            _update_job_state(session, job_id, status="processing", progress=min(progress, 95))

        result = _aggregate_participant_results(
            participant_results,
            intelligence_context=intelligence_context,
            adaptive_layer=participant_results[0]["result"]["fusion_report"].get("adaptive_layer"),
        )

        learning_metadata = _build_learning_metadata(
            structure_report=structure_report,
            fusion_report=result["fusion_report"],
            hqscore=result["score"],
            requested_sampling_rate=requested_sampling_rate,
            research_suggestion_accepted=research_suggestion_accepted,
            adaptive_layer=result["fusion_report"].get("adaptive_layer"),
        )
        continual_learning_manager.persist_job_metadata(session, job_id, learning_metadata)
        train_result = continual_learning_manager.maybe_train(session)
        if train_result.get("trained") and isinstance(result["fusion_report"].get("adaptive_layer"), dict):
            result["fusion_report"]["adaptive_layer"]["model_version"] = train_result.get(
                "model_version",
                result["fusion_report"]["adaptive_layer"].get("model_version", "untrained"),
            )
            result["fusion_report"]["adaptive_layer"]["performance_trend"] = continual_learning_manager.get_performance_trend(session)

        output_path = os.path.join(OUTPUT_DIR, f"{job_id}_fused.csv")
        result["fused_df"].to_csv(output_path, index=False)

        combined_warnings = list(result.get("warnings") or [])
        for warning in (structure_report.get("warnings") or []):
            if isinstance(warning, str):
                combined_warnings.append(warning)
        combined_warnings = list(dict.fromkeys(combined_warnings))
        if combined_warnings:
            existing = result["fusion_report"].get("warnings") or []
            result["fusion_report"]["warnings"] = list(dict.fromkeys([*existing, *combined_warnings]))

        result_status = "completed_with_warnings" if combined_warnings else "completed"

        final_result = {
            "status": result_status,
            "warnings": combined_warnings,
            "structure_report": structure_report,
            "participant_reports": result["participant_reports"],
            "fusion_report": result["fusion_report"],
            "visual_data": result["visual_data"],
            "research_suggestion": research_suggestion,
            "hqscore": result["score"],
            "confidence": result["confidence"],
            "sampling_rate": result["rate"],
            "download": f"/download/{job_id}",
        }

        _update_job_state(
            session,
            job_id,
            status=result_status,
            progress=100,
            result=final_result,
            completed_at=datetime.utcnow(),
            output_path=output_path,
        )
    except FusionPipelineError as exc:
        logger.exception("Fusion job failed with handled pipeline error. job_id=%s", job_id)
        error_payload = exc.to_payload()
        _update_job_state(
            session,
            job_id,
            status="failed",
            progress=100,
            error_payload=error_payload,
            completed_at=datetime.utcnow(),
        )
    except Exception as exc:
        logger.exception("Fusion job failed unexpectedly. job_id=%s", job_id)
        error_type = "fusion_job_failed"
        message = "Fusion processing failed."
        details: dict[str, str] = {}
        if isinstance(exc, pd.errors.MergeError):
            error_type = "dataset_schema_conflict"
            message = "Dataset columns conflict during participant merge."
            details = {"hint": "Check duplicated modality files within the same participant."}
        error_payload = build_error_payload(
            error_type=error_type,
            message=message,
            details=details,
        )
        _update_job_state(
            session,
            job_id,
            status="failed",
            progress=100,
            error_payload=error_payload,
            completed_at=datetime.utcnow(),
        )
    finally:
        session.close()


@app.post("/fuse", response_model=FuseJobCreateResponse)
async def fuse_datasets(
    background_tasks: BackgroundTasks,
    dataset1: UploadFile | None = File(None),
    dataset2: UploadFile | None = File(None),
    dataset3: UploadFile | None = File(None),
    dataset4: UploadFile | None = File(None),
    dataset1_files: list[UploadFile] | None = File(None),
    dataset2_files: list[UploadFile] | None = File(None),
    dataset3_files: list[UploadFile] | None = File(None),
    dataset4_files: list[UploadFile] | None = File(None),
    sampling_rate: float | None = Form(None),
    alignment_mode: str | None = Form(None),
):
    # Error contract for direct request validation failures:
    # {
    #   "status": "failed",
    #   "error_type": "<machine_code>",
    #   "message": "<human-readable>",
    #   "details": {...}
    # }
    job_id = str(uuid.uuid4())
    slot_uploads = [
        ("dataset1", _normalize_slot_uploads(dataset1, dataset1_files)),
        ("dataset2", _normalize_slot_uploads(dataset2, dataset2_files)),
        ("dataset3", _normalize_slot_uploads(dataset3, dataset3_files)),
        ("dataset4", _normalize_slot_uploads(dataset4, dataset4_files)),
    ]

    if not slot_uploads[0][1] or not slot_uploads[1][1]:
        raise FusionPipelineError(
            error_type="missing_required_datasets",
            message="dataset1 and dataset2 are required.",
            details={"required_slots": ["dataset1", "dataset2"]},
        )

    job_upload_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_upload_dir, exist_ok=True)

    slot_dirs: list[tuple[str, str]] = []
    for slot_name, uploads in slot_uploads:
        if not uploads:
            continue
        slot_dir = os.path.join(job_upload_dir, slot_name)
        _save_slot_uploads(slot_dir, uploads)
        slot_dirs.append((slot_name, slot_dir))

    resolved_alignment_mode = _normalize_alignment_mode(alignment_mode)
    _create_job_record(job_id, alignment_mode=resolved_alignment_mode)

    background_tasks.add_task(
        _process_fusion_job,
        job_id,
        slot_dirs,
        sampling_rate,
        None,
        resolved_alignment_mode,
        False,
    )

    return {
        "job_id": job_id,
        "status": "processing",
    }


@app.get("/status/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    # Successful completed-with-warning jobs include:
    # {
    #   "status": "completed_with_warnings",
    #   "result": {"warnings": [...], "fusion_report": {...}, ...}
    # }
    # Failed jobs include:
    # {
    #   "status": "failed",
    #   "error": {"error_type": "...", "message": "...", "details": {...}}
    # }
    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        payload: dict = {
            "job_id": job.id,
            "status": job.status,
            "progress": int(job.progress or 0),
            "error_message": None,
        }

        if job.status in {"completed", "completed_with_warnings"} and job.result_json:
            payload["result"] = json.loads(job.result_json)
        if job.status == "failed" and job.error_message:
            parsed_error = None
            try:
                parsed_error = json.loads(job.error_message)
            except Exception:
                parsed_error = None
            if isinstance(parsed_error, dict):
                payload["error"] = {
                    "error_type": str(parsed_error.get("error_type", "fusion_job_failed")),
                    "message": str(parsed_error.get("message", "Fusion processing failed.")),
                    "details": parsed_error.get("details") if isinstance(parsed_error.get("details"), dict) else {},
                }
                payload["error_message"] = payload["error"]["message"]
            else:
                payload["error"] = {
                    "error_type": "fusion_job_failed",
                    "message": str(job.error_message),
                    "details": {},
                }
                payload["error_message"] = str(job.error_message)

        return payload
    finally:
        session.close()


@app.get("/research_suggestions/{job_id}", response_model=ResearchSuggestionStatusResponse)
def get_research_suggestion(job_id: str):
    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        suggestion = (
            json.loads(job.research_suggestion_json)
            if job.research_suggestion_json
            else None
        )

        return {
            "job_id": job.id,
            "status": job.status,
            "progress": int(job.progress or 0),
            "research_suggestion": suggestion,
        }
    finally:
        session.close()


@app.post("/research_suggestions/{job_id}/apply", response_model=FuseJobCreateResponse)
def apply_research_suggestion(
    job_id: str,
    background_tasks: BackgroundTasks,
    sampling_rate: float | None = None,
    alignment_mode: str | None = None,
):
    session = SessionLocal()
    try:
        source_job = session.query(Job).filter(Job.id == job_id).first()
        if not source_job:
            raise HTTPException(status_code=404, detail="Job not found")

        if not source_job.research_suggestion_json:
            raise HTTPException(status_code=400, detail="Research suggestion not available yet")

        suggestion = json.loads(source_job.research_suggestion_json)
        target_rate = sampling_rate if sampling_rate is not None else suggestion.get("recommended_sampling_rate")
        if target_rate is None:
            raise HTTPException(status_code=400, detail="Suggested sampling rate missing")

        source_root_dir = os.path.join(UPLOAD_DIR, job_id)
        if not os.path.isdir(source_root_dir):
            raise HTTPException(status_code=400, detail="Original uploaded datasets not found")

        source_slot_dirs = [
            (slot_name, os.path.join(source_root_dir, slot_name))
            for slot_name in sorted(os.listdir(source_root_dir))
            if os.path.isdir(os.path.join(source_root_dir, slot_name))
        ]
        if len(source_slot_dirs) < 2:
            raise HTTPException(status_code=400, detail="At least two original datasets are required")

        new_job_id = str(uuid.uuid4())
        new_root_dir = os.path.join(UPLOAD_DIR, new_job_id)
        os.makedirs(new_root_dir, exist_ok=True)

        copied_slot_dirs: list[tuple[str, str]] = []
        for slot_name, source_slot_dir in source_slot_dirs:
            target_slot_dir = os.path.join(new_root_dir, slot_name)
            shutil.copytree(source_slot_dir, target_slot_dir, dirs_exist_ok=True)
            copied_slot_dirs.append((slot_name, target_slot_dir))

        source_alignment_mode = alignment_mode or source_job.alignment_mode
        resolved_alignment_mode = _normalize_alignment_mode(source_alignment_mode)
        _create_job_record(new_job_id, alignment_mode=resolved_alignment_mode)

        background_tasks.add_task(
            _process_fusion_job,
            new_job_id,
            copied_slot_dirs,
            float(target_rate),
            suggestion,
            resolved_alignment_mode,
            True,
        )

        return {
            "job_id": new_job_id,
            "status": "processing",
        }
    finally:
        session.close()


# ---------------------------------------------------------
# SUGGEST ENDPOINT
# ---------------------------------------------------------

@app.post("/suggest")
async def suggest_operations(
    dataset: UploadFile = File(...),
):

    path = os.path.join(UPLOAD_DIR, dataset.filename)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(dataset.file, buffer)

    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception as exc:
        raise FusionPipelineError(
            error_type="invalid_csv",
            message="Invalid or corrupted CSV file.",
            details={"file": dataset.filename or "dataset.csv"},
        ) from exc
    if df.empty or df.shape[1] == 0:
        raise FusionPipelineError(
            error_type="dataset_empty",
            message="Dataset is empty.",
            details={"file": dataset.filename or "dataset.csv"},
        )

    suggestions = fusion_engine.suggest(df)

    return suggestions


# ---------------------------------------------------------
# APPLY SUGGESTION ENDPOINT
# ---------------------------------------------------------

@app.post("/apply")
async def apply_suggestion(
    dataset: UploadFile = File(...),
):

    path = os.path.join(UPLOAD_DIR, dataset.filename)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(dataset.file, buffer)

    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception as exc:
        raise FusionPipelineError(
            error_type="invalid_csv",
            message="Invalid or corrupted CSV file.",
            details={"file": dataset.filename or "dataset.csv"},
        ) from exc
    if df.empty or df.shape[1] == 0:
        raise FusionPipelineError(
            error_type="dataset_empty",
            message="Dataset is empty.",
            details={"file": dataset.filename or "dataset.csv"},
        )

    suggestions = fusion_engine.suggest(df)
    suggestion = suggestions.get("suggestions", {})

    modified_df, validation = fusion_engine.apply(df, suggestion)

    job_id = str(os.urandom(8).hex())
    output_path = os.path.join(OUTPUT_DIR, f"{job_id}_applied.csv")

    modified_df.to_csv(output_path, index=False)

    return {
        "status": "applied" if validation["accepted"] else "rejected",
        "validation": validation,
        "download": f"/download/{job_id}"
    }


# ---------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------

@app.get("/download/{job_id}")
def download(job_id: str):
    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if job and job.output_path and os.path.exists(job.output_path):
            return FileResponse(job.output_path, filename=os.path.basename(job.output_path))
    finally:
        session.close()

    file_path = os.path.join(OUTPUT_DIR, f"{job_id}_fused.csv")

    if not os.path.exists(file_path):
        file_path = os.path.join(OUTPUT_DIR, f"{job_id}_applied.csv")

    return FileResponse(file_path, filename=os.path.basename(file_path))
