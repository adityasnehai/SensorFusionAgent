from __future__ import annotations

import os
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
import pandas as pd

from app.core.exceptions import FusionPipelineError
from app.core.task_inference import infer_task_context
from app.core.modality_registry import MODALITY_REGISTRY
from app.ingestion.llm_schema_inference import infer_schema_with_llm_fallback

TIMESTAMP_HINTS = (
    "timestamp",
    "time",
    "ts",
    "datetime",
    "date_time",
    "recorded_at",
)

SENSOR_PATTERNS: Dict[str, List[str]] = {
    "acc_x": [r"^acc(?:el(?:erometer)?)?[_\- ]?x$", r"^a[_\- ]?x$", r"^ax$"],
    "acc_y": [r"^acc(?:el(?:erometer)?)?[_\- ]?y$", r"^a[_\- ]?y$", r"^ay$"],
    "acc_z": [r"^acc(?:el(?:erometer)?)?[_\- ]?z$", r"^a[_\- ]?z$", r"^az$"],
    "gyro_x": [r"^gyro(?:scope)?[_\- ]?x$", r"^g[_\- ]?x$", r"^wx$"],
    "gyro_y": [r"^gyro(?:scope)?[_\- ]?y$", r"^g[_\- ]?y$", r"^wy$"],
    "gyro_z": [r"^gyro(?:scope)?[_\- ]?z$", r"^g[_\- ]?z$", r"^wz$"],
    "mag_x": [r"^mag(?:netometer)?[_\- ]?x$", r"^m[_\- ]?x$"],
    "mag_y": [r"^mag(?:netometer)?[_\- ]?y$", r"^m[_\- ]?y$"],
    "mag_z": [r"^mag(?:netometer)?[_\- ]?z$", r"^m[_\- ]?z$"],
    "gps_lat": [r"^(gps[_\- ]?)?lat(?:itude)?$"],
    "gps_lon": [r"^(gps[_\- ]?)?lon(?:gitude)?$", r"^(gps[_\- ]?)?lng$"],
    "gps_alt": [r"^(gps[_\- ]?)?alt(?:itude)?$"],
    "gps_speed": [r"^(gps[_\- ]?)?speed$", r"^velocity$"],
    "heart_rate": [r"^(heart[_\- ]?rate|hr|pulse)$"],
    "pressure": [r"^(pressure|baro(?:meter)?)$"],
    "light_lux": [r"^(light|lux|illuminance)$"],
    "proximity": [r"^proximity$"],
}

PARTICIPANT_PREFIX_RE = re.compile(r"^(participant|subject|user|person|p)[_\-]?(\d+)", re.IGNORECASE)
SHORT_PARTICIPANT_RE = re.compile(r"^([a-z]{1,3}\d{1,4})[_\-]", re.IGNORECASE)
MAX_DATASET_ROWS = int(os.getenv("MAX_DATASET_ROWS", "1000000"))
STRICT_MAX_ROWS = os.getenv("STRICT_MAX_ROWS", "0").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class InferredCsv:
    dataframe: pd.DataFrame
    modalities: List[str]
    schema_confidence: float
    schema_method: str
    reasoning_summary: str | None
    timestamp_ambiguous: bool
    warnings: List[str] = field(default_factory=list)


@dataclass
class SlotBundle:
    slot_name: str
    participant_frames: Dict[str, pd.DataFrame]
    files_detected: int
    grouping_strategy: str
    schema_confidence: float
    schema_method: str
    schema_reasoning_summary: str | None
    detected_modalities: List[str]
    timestamp_ambiguous: bool
    warnings: List[str] = field(default_factory=list)


def _safe_realpath(path: str) -> str:
    return os.path.realpath(os.path.abspath(path))


def _safe_join(root: str, relative_path: str) -> str:
    normalized = os.path.normpath(relative_path).lstrip("/\\")
    if normalized.startswith(".."):
        raise ValueError("Path traversal attempt detected")

    target = os.path.join(root, normalized)
    root_real = _safe_realpath(root)
    target_real = _safe_realpath(target)

    if not (target_real == root_real or target_real.startswith(root_real + os.sep)):
        raise ValueError("Unsafe target path")

    return target


def safe_extract_zip(zip_path: str, extract_root: str) -> tuple[list[str], list[str]]:
    os.makedirs(extract_root, exist_ok=True)

    extracted_files: list[str] = []
    warnings: list[str] = []

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            member_name = member.filename or ""
            try:
                target_path = _safe_join(extract_root, member_name)
            except ValueError:
                warnings.append(f"Skipped unsafe ZIP member: {member_name}")
                continue

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with archive.open(member, "r") as source, open(target_path, "wb") as target:
                shutil.copyfileobj(source, target)
            extracted_files.append(target_path)

    return extracted_files, warnings


def _collect_csv_files(root: str, skip_dirs: set[str] | None = None) -> list[str]:
    skip_dirs = skip_dirs or set()
    csv_files: list[str] = []
    for walk_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for filename in files:
            if filename.lower().endswith(".csv"):
                csv_files.append(os.path.join(walk_root, filename))
    return sorted(set(csv_files))


def _normalize_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")


def _infer_timestamp_column(df: pd.DataFrame) -> tuple[str, bool]:
    if df.columns.empty:
        raise FusionPipelineError(
            error_type="dataset_empty",
            message="Dataset is empty.",
            details={"reason": "no_columns"},
        )

    candidates: list[tuple[str, float]] = []
    timestamp_like_columns: list[str] = []

    for column in df.columns:
        normalized = _normalize_label(str(column))
        if any(hint in normalized for hint in TIMESTAMP_HINTS):
            timestamp_like_columns.append(column)
            parsed = pd.to_datetime(df[column], errors="coerce", format="mixed")
            ratio = float(parsed.notna().mean()) if len(parsed) else 0.0
            if ratio > 0:
                candidates.append((column, ratio))

    if not timestamp_like_columns:
        raise FusionPipelineError(
            error_type="missing_timestamp_column",
            message="Timestamp column not found.",
            details={"required_hints": ",".join(TIMESTAMP_HINTS)},
        )

    if not candidates:
        raise FusionPipelineError(
            error_type="invalid_timestamp_format",
            message="Timestamp column not recognized.",
            details={"candidate_columns": ",".join(str(col) for col in timestamp_like_columns[:5])},
        )

    candidates.sort(key=lambda item: item[1], reverse=True)
    ambiguous = len(candidates) > 1 and abs(candidates[0][1] - candidates[1][1]) < 0.1
    return candidates[0][0], ambiguous


def _canonical_column(column_name: str) -> str | None:
    normalized = _normalize_label(column_name)

    if normalized == "timestamp":
        return "timestamp"

    for canonical, regexes in SENSOR_PATTERNS.items():
        for pattern in regexes:
            if re.match(pattern, normalized):
                return canonical

    if normalized in {"acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z", "mag_x", "mag_y", "mag_z"}:
        return normalized

    return None


def _infer_schema(df: pd.DataFrame, timestamp_column: str) -> tuple[dict[str, str], list[str], float]:
    rename_map: dict[str, str] = {}
    mapped_sensor_columns = 0
    sensor_like_columns = 0

    for column in df.columns:
        if column == timestamp_column:
            continue

        normalized = _normalize_label(str(column))
        if any(token in normalized for token in ("acc", "gyro", "mag", "gps", "heart", "hr", "pressure", "light", "prox")):
            sensor_like_columns += 1

        canonical = _canonical_column(str(column))
        if canonical and canonical != column:
            rename_map[column] = canonical
        if canonical and canonical != "timestamp":
            mapped_sensor_columns += 1

    mapped_columns = {rename_map.get(col, col) for col in df.columns}
    detected_modalities = sorted(
        modality
        for modality, config in MODALITY_REGISTRY.items()
        if any(col in mapped_columns for col in config["columns"])
    )

    denominator = max(1, sensor_like_columns)
    confidence = min(1.0, float(mapped_sensor_columns) / float(denominator))

    return rename_map, detected_modalities, round(confidence, 4)


def _read_and_infer_csv(path: str) -> InferredCsv:
    try:
        df = pd.read_csv(path, low_memory=False)
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        raise FusionPipelineError(
            error_type="invalid_csv",
            message="Invalid or corrupted CSV file.",
            details={"file": os.path.basename(path), "reason": str(exc)},
        ) from exc
    except Exception as exc:
        raise FusionPipelineError(
            error_type="invalid_csv",
            message="Invalid or corrupted CSV file.",
            details={"file": os.path.basename(path)},
        ) from exc

    if df.shape[1] == 0 or len(df) == 0:
        raise FusionPipelineError(
            error_type="dataset_empty",
            message="Dataset is empty.",
            details={"file": os.path.basename(path)},
        )

    warnings: list[str] = []
    if len(df) > MAX_DATASET_ROWS:
        if STRICT_MAX_ROWS:
            raise FusionPipelineError(
                error_type="dataset_too_large",
                message="Dataset too large.",
                details={
                    "file": os.path.basename(path),
                    "max_rows": MAX_DATASET_ROWS,
                    "rows": int(len(df)),
                },
            )

        step = int(np.ceil(len(df) / float(MAX_DATASET_ROWS)))
        step = max(1, step)
        df = df.iloc[::step].copy()
        warnings.append(
            f"{os.path.basename(path)} exceeded {MAX_DATASET_ROWS} rows; downsampled automatically."
        )

    timestamp_col, ambiguous = _infer_timestamp_column(df)
    rename_map, modalities, confidence = _infer_schema(df, timestamp_col)
    schema_method = "rule_based"
    reasoning_summary: str | None = "Rule-based pattern matching from column names."

    llm_result = infer_schema_with_llm_fallback(
        df,
        timestamp_column=timestamp_col,
        rule_confidence=confidence,
    )
    if llm_result.get("accepted"):
        llm_mapping = llm_result.get("schema_mapping") or {}
        if isinstance(llm_mapping, dict):
            for source_col, target_col in llm_mapping.items():
                if (
                    source_col in df.columns
                    and source_col != timestamp_col
                    and isinstance(target_col, str)
                    and target_col != "unknown"
                    and source_col != target_col
                ):
                    rename_map[source_col] = target_col

        schema_method = "llm"
        reasoning_summary = llm_result.get("reasoning_summary") or reasoning_summary

        provisional_df = df.rename(columns=rename_map)
        inferred_timestamp_col = "timestamp" if timestamp_col in rename_map else timestamp_col
        _, modalities, confidence = _infer_schema(provisional_df, inferred_timestamp_col)
        confidence = max(confidence, float(llm_result.get("confidence", confidence)))

    if timestamp_col != "timestamp":
        rename_map[timestamp_col] = "timestamp"

    df = df.rename(columns=rename_map)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed")
    df = df.dropna(subset=["timestamp"]) 
    if df.empty:
        raise FusionPipelineError(
            error_type="invalid_timestamp_format",
            message="Timestamp column not recognized.",
            details={"file": os.path.basename(path)},
        )

    ignored_non_numeric: list[str] = []
    for modality_cfg in MODALITY_REGISTRY.values():
        for col in modality_cfg["columns"]:
            if col not in df.columns:
                continue

            if pd.api.types.is_numeric_dtype(df[col]):
                continue

            coerced = pd.to_numeric(df[col], errors="coerce")
            if coerced.notna().sum() == 0:
                ignored_non_numeric.append(col)
                df = df.drop(columns=[col], errors="ignore")
                continue

            df[col] = coerced

    if ignored_non_numeric:
        warnings.append(
            "Non-numeric columns ignored."
            + f" ({', '.join(sorted(set(ignored_non_numeric)))})"
        )

    df = df.loc[:, ~df.columns.duplicated()]
    df = df.sort_values("timestamp")

    return InferredCsv(
        dataframe=df,
        modalities=modalities,
        schema_confidence=round(float(confidence), 4),
        schema_method=schema_method,
        reasoning_summary=reasoning_summary,
        timestamp_ambiguous=ambiguous,
        warnings=warnings,
    )


def _group_by_folder_or_filename(csv_paths: list[str], slot_root: str) -> tuple[dict[str, list[str]], str]:
    relative = [os.path.relpath(path, slot_root) for path in csv_paths]

    participant_from_path: list[str | None] = []
    normalized_parts: list[list[str]] = []
    for rel in relative:
        parts = rel.split(os.sep)
        if parts and parts[0] == "_zip_extract":
            parts = parts[1:]
        if parts and re.match(r"^archive_\d+$", parts[0]) and len(parts) > 1:
            parts = parts[1:]
        normalized_parts.append(parts)

        participant_token: str | None = None
        for token in parts:
            normalized = _normalize_label(token)
            match = PARTICIPANT_PREFIX_RE.match(normalized)
            if match:
                participant_token = f"{match.group(1).lower()}_{match.group(2)}"
                break
        participant_from_path.append(participant_token)

    grouped_by_path_participant: dict[str, list[str]] = {}
    for participant, abs_path in zip(participant_from_path, csv_paths):
        if participant:
            grouped_by_path_participant.setdefault(participant, []).append(abs_path)

    if len(grouped_by_path_participant) >= 2:
        return grouped_by_path_participant, "folder_based"

    grouped_by_name: dict[str, list[str]] = {}
    for path in csv_paths:
        filename = os.path.basename(path)
        stem = os.path.splitext(filename)[0]
        participant = None

        match = PARTICIPANT_PREFIX_RE.match(stem)
        if match:
            participant = f"{match.group(1).lower()}_{match.group(2)}"
        else:
            short = SHORT_PARTICIPANT_RE.match(stem)
            if short:
                participant = short.group(1).lower()

        if participant:
            grouped_by_name.setdefault(participant, []).append(path)

    if len(grouped_by_name) >= 2:
        return grouped_by_name, "filename_prefix"

    return {"participant_01": list(csv_paths)}, "single_group"


def _merge_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        raise FusionPipelineError(
            error_type="invalid_dataset_content",
            message="No frames available to merge.",
            details={},
        )

    def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
        normalized = df.copy()
        normalized = normalized.loc[:, ~normalized.columns.duplicated()]
        normalized = normalized.sort_values("timestamp")
        if normalized["timestamp"].duplicated().any():
            # Collapse duplicate timestamps within a file to avoid cartesian-expansion during fusion.
            normalized = (
                normalized.groupby("timestamp", as_index=False)
                .first()
                .sort_values("timestamp")
            )
        return normalized

    merged = _normalize_frame(frames[0]).set_index("timestamp")

    for frame in frames[1:]:
        current = _normalize_frame(frame).set_index("timestamp")
        # combine_first merges on timestamp index and reuses same canonical column names
        # without introducing suffix collisions (e.g., acc_x_dup, acc_x_dup_dup).
        merged = merged.combine_first(current)

    merged = merged.reset_index()
    merged = merged.loc[:, ~merged.columns.duplicated()]
    merged = merged.sort_values("timestamp")
    return merged


def build_slot_bundle(slot_name: str, slot_root: str, max_csv_files: int = 250) -> SlotBundle:
    extraction_root = os.path.join(slot_root, "_zip_extract")
    os.makedirs(extraction_root, exist_ok=True)
    try:
        warnings: list[str] = []
        zip_files: list[str] = []
        extracted_roots: list[str] = []

        for walk_root, _, files in os.walk(slot_root):
            for filename in files:
                if filename.lower().endswith(".zip"):
                    zip_files.append(os.path.join(walk_root, filename))

        for index, zip_path in enumerate(sorted(set(zip_files))):
            target = os.path.join(extraction_root, f"archive_{index + 1}")
            _, zip_warnings = safe_extract_zip(zip_path, target)
            warnings.extend(zip_warnings)
            extracted_roots.append(target)

        csv_files = _collect_csv_files(slot_root, skip_dirs={"_zip_extract"})
        for extracted_root in extracted_roots:
            csv_files.extend(_collect_csv_files(extracted_root))
        csv_files = sorted(set(csv_files))
        if len(csv_files) > max_csv_files:
            raise FusionPipelineError(
                error_type="too_many_files",
                message="CSV file limit exceeded.",
                details={
                    "slot": slot_name,
                    "files_detected": int(len(csv_files)),
                    "max_csv_files": int(max_csv_files),
                },
            )

        if not csv_files:
            raise FusionPipelineError(
                error_type="no_csv_files",
                message="No CSV files detected.",
                details={"slot": slot_name},
            )

        grouped_files, grouping_strategy = _group_by_folder_or_filename(csv_files, slot_root)

        participant_frames: dict[str, pd.DataFrame] = {}
        detected_modalities: set[str] = set()
        confidence_scores: list[float] = []
        schema_methods: list[str] = []
        schema_reasoning: list[str] = []
        timestamp_ambiguous = False
        critical_errors: list[FusionPipelineError] = []

        for participant_id, files in grouped_files.items():
            inferred_frames: list[pd.DataFrame] = []

            for file_path in files:
                try:
                    inferred = _read_and_infer_csv(file_path)
                except FusionPipelineError as exc:
                    if exc.error_type in {
                        "dataset_empty",
                        "invalid_csv",
                        "invalid_timestamp_format",
                        "missing_timestamp_column",
                        "dataset_too_large",
                    }:
                        critical_errors.append(exc)
                    warnings.append(
                        f"{slot_name}/{participant_id}: skipped {os.path.basename(file_path)} ({exc.message})"
                    )
                    continue
                except Exception as exc:
                    warnings.append(f"{slot_name}/{participant_id}: skipped {os.path.basename(file_path)} ({exc})")
                    continue

                inferred_frames.append(inferred.dataframe)
                detected_modalities.update(inferred.modalities)
                confidence_scores.append(inferred.schema_confidence)
                schema_methods.append(inferred.schema_method)
                if inferred.reasoning_summary:
                    schema_reasoning.append(str(inferred.reasoning_summary))
                timestamp_ambiguous = timestamp_ambiguous or inferred.timestamp_ambiguous
                warnings.extend(inferred.warnings)

                if len(inferred.dataframe) <= 1:
                    warnings.append(
                        f"{slot_name}/{participant_id}: dataset has 1 row; advanced metrics may be skipped."
                    )

            if not inferred_frames:
                continue

            merged = _merge_frames(inferred_frames)
            merged["participant_id"] = participant_id
            participant_frames[participant_id] = merged

        if critical_errors:
            # Do not silently continue when any file is critically malformed.
            # This keeps API behavior explicit for invalid/corrupted uploads.
            raise critical_errors[0]

        if not participant_frames:
            raise FusionPipelineError(
                error_type="invalid_dataset_content",
                message=f"{slot_name}: no valid participant dataframes after parsing",
                details={"slot": slot_name},
            )

        schema_confidence = round(sum(confidence_scores) / len(confidence_scores), 4) if confidence_scores else 0.0
        schema_method = "llm" if any(method == "llm" for method in schema_methods) else "rule_based"
        schema_reasoning_summary = "; ".join(dict.fromkeys(schema_reasoning))[:600] if schema_reasoning else None

        bundle = SlotBundle(
            slot_name=slot_name,
            participant_frames=participant_frames,
            files_detected=len(csv_files),
            grouping_strategy=grouping_strategy,
            schema_confidence=schema_confidence,
            schema_method=schema_method,
            schema_reasoning_summary=schema_reasoning_summary,
            detected_modalities=sorted(detected_modalities),
            timestamp_ambiguous=timestamp_ambiguous,
            warnings=warnings,
        )
        return bundle
    finally:
        shutil.rmtree(extraction_root, ignore_errors=True)


def build_fusion_inputs(
    slot_dirs: list[tuple[str, str]],
    max_csv_files: int = 250,
) -> tuple[dict[str, list[pd.DataFrame]], list[pd.DataFrame], dict, dict]:
    bundles: list[SlotBundle] = [
        build_slot_bundle(slot_name=slot_name, slot_root=slot_dir, max_csv_files=max_csv_files)
        for slot_name, slot_dir in slot_dirs
    ]

    participant_ids = sorted({pid for bundle in bundles for pid in bundle.participant_frames.keys()})

    participant_inputs: dict[str, list[pd.DataFrame]] = {}
    for participant_id in participant_ids:
        frames = [
            bundle.participant_frames[participant_id]
            .drop(columns=["participant_id"], errors="ignore")
            .copy()
            for bundle in bundles
            if participant_id in bundle.participant_frames
        ]
        if len(frames) >= 2:
            participant_inputs[participant_id] = frames

    # Fallback path: if participant names do not match across slots, fuse at slot level.
    if not participant_inputs and len(bundles) >= 2:
        global_frames = []
        for bundle in bundles:
            concatenated = pd.concat(bundle.participant_frames.values(), ignore_index=True)
            concatenated = concatenated.drop(columns=["participant_id"], errors="ignore")
            concatenated = concatenated.sort_values("timestamp")
            global_frames.append(concatenated)
        participant_inputs["global"] = global_frames

    research_frames: list[pd.DataFrame] = []
    for bundle in bundles:
        combined = pd.concat(bundle.participant_frames.values(), ignore_index=True)
        combined = combined.drop(columns=["participant_id"], errors="ignore")
        if len(combined) > 12000:
            combined = combined.iloc[:12000].copy()
        research_frames.append(combined)

    grouping_values = {bundle.grouping_strategy for bundle in bundles}
    grouping_strategy = grouping_values.pop() if len(grouping_values) == 1 else "mixed"

    structure_report = {
        "participants_detected": len(participant_ids),
        "files_detected": sum(bundle.files_detected for bundle in bundles),
        "grouping_strategy": grouping_strategy,
        "schema_inference_confidence": round(
            sum(bundle.schema_confidence for bundle in bundles) / max(1, len(bundles)),
            4,
        ),
        "detected_modalities": sorted(
            {
                modality
                for bundle in bundles
                for modality in bundle.detected_modalities
            }
        ),
        "timestamp_ambiguous": any(bundle.timestamp_ambiguous for bundle in bundles),
        "warnings": [warning for bundle in bundles for warning in bundle.warnings][:25],
    }

    schema_method = "llm" if any(bundle.schema_method == "llm" for bundle in bundles) else "rule_based"
    schema_confidence = round(
        sum(bundle.schema_confidence for bundle in bundles) / max(1, len(bundles)),
        4,
    )
    schema_reasoning_fragments = [
        bundle.schema_reasoning_summary
        for bundle in bundles
        if bundle.schema_reasoning_summary
    ]
    schema_reasoning_summary = "; ".join(dict.fromkeys(schema_reasoning_fragments))[:800] if schema_reasoning_fragments else None

    task_inference = infer_task_context(
        research_frames,
        detected_modalities=structure_report["detected_modalities"],
        llm_reasoning_summary=schema_reasoning_summary,
    )

    intelligence_context = {
        "schema_inference": {
            "method": schema_method,
            "confidence": schema_confidence,
            "reasoning_summary": schema_reasoning_summary,
        },
        "task_inference": task_inference,
    }

    return participant_inputs, research_frames, structure_report, intelligence_context
