import os
import pandas as pd
import numpy as np
import time
from app.agent.runtime import AgenticRuntime
from app.core.modality_registry import MODALITY_REGISTRY
from app.core.time_alignment import estimate_offset
from app.core.drift_analysis import analyze_drift
from app.core.hqscore_v4 import compute_hqscore_v4
from app.core.exceptions import FusionPipelineError


class HarmonizationLoop:

    def __init__(self, max_iterations=3):
        self.max_iterations = max_iterations
        self.agentic_runtime_enabled = self._env_flag("AGENTIC_RUNTIME_ENABLED", "1")
        self.agentic_min_improvement = float(os.getenv("AGENTIC_MIN_IMPROVEMENT", "0.002"))
        self.agentic_eval_max_rows = int(os.getenv("AGENTIC_EVAL_MAX_ROWS", "50000"))

    def _env_flag(self, key, default="0"):
        value = str(os.getenv(key, default)).strip().lower()
        return value in {"1", "true", "yes", "on"}

    # -------------------------------------------------
    # Ensure Timestamp Exists + Datetime Format
    # -------------------------------------------------

    def _prepare_timestamp(self, df):

        if "timestamp" not in df.columns:
            raise FusionPipelineError(
                error_type="missing_timestamp_column",
                message="Timestamp column not found.",
                details={"required_column": "timestamp"},
            )

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
            format="mixed"
        )

        df = df.dropna(subset=["timestamp"])
        if df.empty:
            raise FusionPipelineError(
                error_type="invalid_timestamp_format",
                message="Timestamp column not recognized.",
                details={},
            )

        return df

    # -------------------------------------------------
    # Estimate Sampling Rate
    # -------------------------------------------------

    def _estimate_sampling_rate(self, df):

        diffs = df["timestamp"].diff().dt.total_seconds().dropna()

        if len(diffs) == 0:
            return 1.0

        median = diffs.median()

        if median <= 0:
            return 1.0

        return round(1.0 / median, 2)

    # -------------------------------------------------
    # Determine Master Rate (Lowest Safe)
    # -------------------------------------------------

    def _determine_master_rate(self, datasets):

        rates = [self._estimate_sampling_rate(df) for df in datasets]

        valid = [r for r in rates if r > 0]

        return min(valid) if valid else 10

    # -------------------------------------------------
    # Timestamp Helpers
    # -------------------------------------------------

    def _to_iso(self, ts):
        if ts is None or pd.isna(ts):
            return None
        return ts.isoformat()

    def _duration_seconds(self, df):
        if len(df) == 0:
            return 0.0

        start = df["timestamp"].min()
        end = df["timestamp"].max()

        if pd.isna(start) or pd.isna(end):
            return 0.0

        return round(max(0.0, (end - start).total_seconds()), 3)

    def _overlap_window(self, datasets):
        starts = [df["timestamp"].min() for df in datasets if len(df) > 0]
        ends = [df["timestamp"].max() for df in datasets if len(df) > 0]

        if not starts or not ends:
            return {
                "start_timestamp": None,
                "end_timestamp": None,
                "duration_seconds": 0.0,
            }

        overlap_start = max(starts)
        overlap_end = min(ends)

        if pd.isna(overlap_start) or pd.isna(overlap_end) or overlap_start >= overlap_end:
            return {
                "start_timestamp": None,
                "end_timestamp": None,
                "duration_seconds": 0.0,
            }

        return {
            "start_timestamp": self._to_iso(overlap_start),
            "end_timestamp": self._to_iso(overlap_end),
            "duration_seconds": round((overlap_end - overlap_start).total_seconds(), 3),
        }

    # -------------------------------------------------
    # Build Master Time Grid
    # -------------------------------------------------

    def _build_master_grid(self, datasets, target_rate):

        starts = [df["timestamp"].min() for df in datasets]
        ends = [df["timestamp"].max() for df in datasets]

        start = max(starts)
        end = min(ends)

        if start > end:
            raise FusionPipelineError(
                error_type="no_time_overlap",
                message="Datasets do not overlap in time.",
                details={},
            )
        if start == end:
            return pd.DatetimeIndex([start])

        freq_ms = int(1000 / target_rate)

        return pd.date_range(
            start=start,
            end=end,
            freq=f"{freq_ms}ms"
        )

    def _check_timeout(self, deadline_monotonic):
        if deadline_monotonic is None:
            return
        if time.monotonic() > deadline_monotonic:
            raise FusionPipelineError(
                error_type="processing_timeout",
                message="Fusion processing timed out.",
                details={},
            )

    def _modality_count(self, merged_df):
        count = 0
        for _, config in MODALITY_REGISTRY.items():
            cols = [col for col in config["columns"] if col in merged_df.columns]
            if cols:
                count += 1
        return count

    # -------------------------------------------------
    # Offset Alignment (IMU-based)
    # -------------------------------------------------

    def _align_offsets(self, datasets, rate, alignment_mode="classical"):

        base = datasets[0]
        aligned = [base]
        offset_seconds = [0.0]

        for df in datasets[1:]:

            df = df.copy()
            lag = estimate_offset(base, df)
            offset = float(lag * (1 / rate)) if rate > 0 else 0.0

            offset = float(np.clip(offset, -5.0, 5.0))

            if abs(offset) > 1e-9:
                df["timestamp"] = df["timestamp"] + pd.to_timedelta(
                    offset,
                    unit="s"
                )

            aligned.append(df)
            offset_seconds.append(round(offset, 4))

        return aligned, offset_seconds

    # -------------------------------------------------
    # Modality-Aware Resampling
    # -------------------------------------------------

    def _resample_dataset(self, df, master_index):

        df = df.set_index("timestamp")
        df = df.reindex(master_index)

        for modality, config in MODALITY_REGISTRY.items():

            for col in config["columns"]:

                if col in df.columns:

                    if config["interp"] == "linear":
                        df[col] = df[col].interpolate(method="time")

                    elif config["interp"] == "ffill":
                        # Pandas 2.2+ removed fillna(method=...), so use dedicated forward-fill.
                        df[col] = df[col].ffill()

        df = df.reset_index().rename(columns={"index": "timestamp"})

        return df

    # -------------------------------------------------
    # Clean Duplicate Columns
    # -------------------------------------------------

    def _clean_columns(self, df):
        # Remove duplicate columns from merges.
        df = df.loc[:, ~df.columns.duplicated()]

        # Coalesce legacy *_dup columns into canonical base columns.
        dup_columns = [col for col in df.columns if col.endswith("_dup")]
        for dup_col in dup_columns:
            base_col = dup_col[:-4]
            if base_col in df.columns:
                left = df[base_col]
                right = df[dup_col]
                left_num = pd.to_numeric(left, errors="coerce")
                right_num = pd.to_numeric(right, errors="coerce")
                if left_num.notna().any() or right_num.notna().any():
                    df[base_col] = left_num.where(left_num.notna(), right_num)
                else:
                    df[base_col] = left.where(left.notna(), right)
            else:
                df = df.rename(columns={dup_col: base_col})

        if dup_columns:
            df = df.drop(columns=dup_columns, errors="ignore")

        # participant_id is appended at aggregate stage; drop any carryover copies.
        participant_cols = [col for col in df.columns if col.startswith("participant_id")]
        if participant_cols:
            df = df.drop(columns=participant_cols, errors="ignore")

        # Sort by timestamp
        df = df.sort_values("timestamp")

        return df

    def _fuse_resampled_datasets(self, resampled):
        if not resampled:
            return pd.DataFrame(columns=["timestamp"])

        fused = pd.DataFrame({"timestamp": resampled[0]["timestamp"]})
        all_columns = sorted({col for df in resampled for col in df.columns if col != "timestamp"})

        for col in all_columns:
            series_candidates = [df[col] for df in resampled if col in df.columns]
            if not series_candidates:
                continue

            numeric_candidates = [pd.to_numeric(series, errors="coerce") for series in series_candidates]
            has_numeric_signal = any(series.notna().any() for series in numeric_candidates)

            if has_numeric_signal:
                stacked = pd.concat(numeric_candidates, axis=1)
                # Fusion policy: mean across available aligned dataset values.
                fused[col] = stacked.mean(axis=1, skipna=True)
                continue

            stacked_raw = pd.concat([series.astype("string") for series in series_candidates], axis=1)
            fused[col] = stacked_raw.bfill(axis=1).iloc[:, 0].astype("object")

        return fused

    # -------------------------------------------------
    # Transparency Metrics
    # -------------------------------------------------

    def _resampling_strategy(self, dataset_rate, master_rate):
        if dataset_rate > master_rate + 1e-6:
            base = "downsample"
        elif dataset_rate < master_rate - 1e-6:
            base = "upsample"
        else:
            base = "native-rate alignment"
        return f"{base} + modality interpolation"

    def _detect_drift(self, rates, master_rate):
        if len(rates) < 2:
            return False
        spread = float(np.std(np.array(rates, dtype=float)))
        threshold = max(0.05, 0.15 * master_rate)
        return bool(spread > threshold)

    def _modality_missingness(self, merged_df):
        missing_modalities = []
        missingness_percentage_by_modality = {}

        for modality, config in MODALITY_REGISTRY.items():
            cols = [col for col in config["columns"] if col in merged_df.columns]
            if not cols:
                missing_modalities.append(modality)
                missingness_percentage_by_modality[modality] = 100.0
                continue

            ratio = float(merged_df[cols].isna().mean().mean() * 100.0)
            missingness_percentage_by_modality[modality] = round(ratio, 2)

        return missing_modalities, missingness_percentage_by_modality

    def _distribution_divergence_score(self, resampled):
        pair_scores = []

        for i in range(len(resampled)):
            left = resampled[i].select_dtypes(include=np.number)

            for j in range(i + 1, len(resampled)):
                right = resampled[j].select_dtypes(include=np.number)
                common_cols = [col for col in left.columns if col in right.columns]

                for col in common_cols:
                    left_series = left[col]
                    right_series = right[col]
                    valid = left_series.notna() & right_series.notna()

                    if valid.sum() < 3:
                        continue

                    left_valid = left_series[valid]
                    right_valid = right_series[valid]

                    denom = float(left_valid.std(ddof=0) + right_valid.std(ddof=0)) + 1e-9
                    normalized_gap = float(abs(left_valid.mean() - right_valid.mean()) / denom)
                    # Compress into [0, 1], where 0 means distributions are closely aligned.
                    pair_scores.append(min(1.0, normalized_gap / 3.0))

        if not pair_scores:
            return 0.0

        return round(float(np.mean(pair_scores)), 4)

    def _confidence_from_score(self, score, missing_modalities_count, divergence_score, drift_type="none"):
        if score >= 0.8:
            level = "High"
        elif score >= 0.55:
            level = "Medium"
        else:
            level = "Low"

        reason = (
            f"HQScore={score:.3f}, missing modalities={missing_modalities_count}, "
            f"distribution divergence={divergence_score:.3f}, drift={drift_type}."
        )
        return {"level": level, "reason": reason}

    def _build_magnitude_overlay(self, resampled, components, max_rows=1000):
        if not resampled:
            return []

        row_count = min(max_rows, len(resampled[0]))
        dataset_magnitudes = {}

        for i, df in enumerate(resampled):
            dataset_key = f"dataset_{i + 1}"

            if all(col in df.columns for col in components):
                numeric = df[list(components)].apply(pd.to_numeric, errors="coerce")
                magnitude = np.sqrt((numeric ** 2).sum(axis=1))
                magnitude = magnitude.where(numeric.notna().all(axis=1), np.nan)
                dataset_magnitudes[dataset_key] = magnitude
            else:
                dataset_magnitudes[dataset_key] = pd.Series(
                    [np.nan] * len(df),
                    index=df.index,
                    dtype=float,
                )

        points = []
        timestamps = resampled[0]["timestamp"].iloc[:row_count]

        for idx in range(row_count):
            row = {
                "timestamp": self._to_iso(timestamps.iloc[idx]),
            }

            for dataset_key, series in dataset_magnitudes.items():
                value = series.iloc[idx]
                row[dataset_key] = None if pd.isna(value) else round(float(value), 6)

            points.append(row)

        return points

    # -------------------------------------------------
    # Main Run
    # -------------------------------------------------

    def run(
        self,
        datasets,
        progress_callback=None,
        target_sampling_rate=None,
        schema_inference=None,
        task_inference=None,
        alignment_mode="classical",
        timeout_seconds=None,
    ):

        if not isinstance(datasets, list):
            raise FusionPipelineError(
                error_type="invalid_input",
                message="Datasets must be provided as a list.",
                details={},
            )

        if len(datasets) < 2 or len(datasets) > 4:
            raise FusionPipelineError(
                error_type="invalid_dataset_count",
                message="Minimum 2 and maximum 4 datasets supported.",
                details={"min_required": 2, "max_allowed": 4, "received": len(datasets)},
            )

        warnings: list[str] = []
        deadline_monotonic = None
        if timeout_seconds is not None:
            deadline_monotonic = time.monotonic() + max(1.0, float(timeout_seconds))
        self._check_timeout(deadline_monotonic)

        # Prepare datasets
        prepared = []

        for df in datasets:
            df = df.copy()
            df = df.drop(columns=[col for col in df.columns if col.startswith("participant_id")], errors="ignore")
            df = self._prepare_timestamp(df)
            df = df.sort_values("timestamp")
            if len(df) <= 1:
                warnings.append("Dataset has a single row; advanced metrics were reduced.")
            prepared.append(df)
        self._check_timeout(deadline_monotonic)

        agentic_layer = {
            "enabled": bool(self.agentic_runtime_enabled),
            "used": False,
            "policy": "disabled",
            "iterations": 0,
            "initial_quality_score": 0.0,
            "final_quality_score": 0.0,
            "net_improvement": 0.0,
            "confidence": 0.0,
            "accepted_actions": [],
            "rejected_actions": [],
            "stop_reason": "disabled",
        }
        if self.agentic_runtime_enabled:
            try:
                runtime = AgenticRuntime(
                    max_iterations=self.max_iterations,
                    min_improvement=self.agentic_min_improvement,
                    evaluation_max_rows=self.agentic_eval_max_rows,
                )
                prepared, agentic_layer = runtime.run(prepared)
                if agentic_layer.get("used"):
                    warnings.append(
                        f"Agentic optimization applied {int(agentic_layer.get('iterations', 0))} action(s)."
                    )
            except Exception as exc:
                warnings.append("Agentic runtime fallback activated.")
                agentic_layer = {
                    "enabled": True,
                    "used": False,
                    "policy": "greedy_safe_search_v1",
                    "iterations": 0,
                    "initial_quality_score": 0.0,
                    "final_quality_score": 0.0,
                    "net_improvement": 0.0,
                    "confidence": 0.0,
                    "accepted_actions": [],
                    "rejected_actions": [],
                    "stop_reason": "runtime_error",
                    "error": str(exc),
                }

        # Determine master rate
        dataset_rates = [self._estimate_sampling_rate(df) for df in prepared]
        auto_master_rate = self._determine_master_rate(prepared)
        master_rate = auto_master_rate
        requested_sampling_rate = None
        suggested_sampling_rate_applied = False

        if target_sampling_rate is not None:
            requested_sampling_rate = float(target_sampling_rate)
            valid_rates = [r for r in dataset_rates if r > 0]

            # Validation/safety gate: only accept suggested rate within sane bounds
            # derived from observed data; otherwise keep auto-selected master rate.
            if valid_rates and requested_sampling_rate > 0:
                min_rate = min(valid_rates)
                max_rate = max(valid_rates)
                lower_bound = max(0.5, min_rate * 0.5)
                upper_bound = max_rate * 2.0
                if lower_bound <= requested_sampling_rate <= upper_bound:
                    master_rate = requested_sampling_rate
                    suggested_sampling_rate_applied = True
        if progress_callback:
            progress_callback(25)
        self._check_timeout(deadline_monotonic)

        # Transformer mode has been removed; classical alignment is always used.
        alignment_mode = "classical"

        # Align offsets
        aligned, offset_seconds = self._align_offsets(
            prepared,
            master_rate,
            alignment_mode=alignment_mode,
        )
        if progress_callback:
            progress_callback(40)
        self._check_timeout(deadline_monotonic)

        # Build master grid
        master_grid = self._build_master_grid(aligned, master_rate)
        self._check_timeout(deadline_monotonic)

        # Resample all datasets
        resampled = [
            self._resample_dataset(df, master_grid)
            for df in aligned
        ]
        if progress_callback:
            progress_callback(60)
        self._check_timeout(deadline_monotonic)

        # Fuse aligned datasets into one canonical schema.
        merged = self._fuse_resampled_datasets(resampled)
        merged = self._clean_columns(merged)
        if progress_callback:
            progress_callback(75)
        self._check_timeout(deadline_monotonic)

        short_dataset = any(len(df) <= 1 for df in resampled)
        if short_dataset:
            drift_analysis = {
                "drift_detected": False,
                "drift_type": "none",
                "average_window_offset": 0.0,
                "dtw_score": 0.0,
                "stability_score": 0.7,
                "offset_trend": [],
                "explanation": "Insufficient rows for drift analysis.",
            }
        else:
            drift_analysis = analyze_drift(resampled, master_rate, max_points=2000)

        provisional_merged = merged
        modality_count = self._modality_count(provisional_merged)
        limited_modality = modality_count <= 1
        if limited_modality:
            warnings.append("Limited modality available.")

        effective_task_inference = task_inference.copy() if isinstance(task_inference, dict) else {}
        if limited_modality:
            effective_task_inference["hqscore_weight_profile"] = "distribution_coverage"

        hqscore_v4 = compute_hqscore_v4(
            merged_df=merged,
            resampled=resampled,
            sampling_rate_hz=master_rate,
            drift_analysis=drift_analysis,
            task_inference=effective_task_inference,
            disable_advanced=short_dataset,
            limited_modality=limited_modality,
        )
        score = float(hqscore_v4["overall"])
        if progress_callback:
            progress_callback(90)
        self._check_timeout(deadline_monotonic)
        missing_modalities, missingness_by_modality = self._modality_missingness(merged)
        divergence_score = self._distribution_divergence_score(resampled)
        confidence = self._confidence_from_score(
            score,
            len(missing_modalities),
            divergence_score,
            drift_analysis.get("drift_type", "none"),
        )
        drift_detected = bool(
            drift_analysis.get("drift_detected", False)
            or self._detect_drift(dataset_rates, master_rate)
        )

        dataset_metrics = []
        for i, df in enumerate(prepared):
            dataset_metrics.append({
                "dataset_id": f"dataset{i + 1}",
                "sampling_rate_hz": round(float(dataset_rates[i]), 4),
                "duration_seconds": self._duration_seconds(df),
                "start_timestamp": self._to_iso(df["timestamp"].min()),
                "end_timestamp": self._to_iso(df["timestamp"].max()),
            })

        resampling_strategy = {
            f"dataset{i + 1}": self._resampling_strategy(dataset_rates[i], master_rate)
            for i in range(len(dataset_rates))
        }

        fusion_report = {
            "dataset_metadata": {
                "datasets": dataset_metrics,
                "overlap_window": self._overlap_window(aligned),
            },
            "alignment_decisions": {
                "master_sampling_rate_hz": round(float(master_rate), 4),
                "offset_corrections": [
                    {
                        "dataset_id": f"dataset{i + 1}",
                        "offset_seconds": round(float(offset_seconds[i]), 4),
                    }
                    for i in range(len(offset_seconds))
                ],
                "drift_detected": drift_detected,
                "resampling_strategy": resampling_strategy,
                "alignment_mode": alignment_mode,
                "requested_sampling_rate_hz": requested_sampling_rate,
                "suggested_sampling_rate_applied": suggested_sampling_rate_applied,
            },
            "data_integrity": {
                "missing_modalities": missing_modalities,
                "missingness_percentage_by_modality": missingness_by_modality,
                "distribution_divergence_score": divergence_score,
            },
            "hqscore": round(float(score), 4),
            "hqscore_v4": hqscore_v4,
            "drift_analysis": drift_analysis,
            "confidence": confidence,
            "summary": (
                f"Fused {len(prepared)} datasets at {master_rate:.2f} Hz. "
                f"HQScore {score:.3f} ({confidence['level']} confidence)."
            ),
            "agentic_layer": agentic_layer,
        }
        if isinstance(schema_inference, dict):
            fusion_report["schema_inference"] = schema_inference
        if isinstance(task_inference, dict):
            fusion_report["task_inference"] = task_inference
        if warnings:
            fusion_report["warnings"] = list(dict.fromkeys(warnings))

        visual_data = {
            "acc_magnitude_overlay": self._build_magnitude_overlay(
                resampled,
                ("acc_x", "acc_y", "acc_z"),
                max_rows=1000,
            ),
            "gyro_magnitude_overlay": self._build_magnitude_overlay(
                resampled,
                ("gyro_x", "gyro_y", "gyro_z"),
                max_rows=1000,
            ),
            "drift_offset_trend": drift_analysis.get("offset_trend", [])[:1000],
        }

        return merged, score, master_rate, fusion_report, confidence, visual_data
