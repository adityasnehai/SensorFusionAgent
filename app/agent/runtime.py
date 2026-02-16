from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.agent.executor import TransformationExecutor
from app.agent.observer import Observer
from app.agent.planner import Planner
from app.core.hqscore_v4 import compute_hqscore_v4


@dataclass
class AgentAction:
    action_id: str
    dataset_index: int
    type: str
    parameters: dict[str, Any]
    rationale: str
    source: str = "planner"


class AgenticRuntime:
    """Runs a safe, greedy plan/execute/observe loop before fusion."""

    def __init__(
        self,
        max_iterations: int = 3,
        min_improvement: float = 0.002,
        evaluation_max_rows: int = 50000,
    ) -> None:
        self.max_iterations = max(1, int(max_iterations))
        self.min_improvement = float(min_improvement)
        self.evaluation_max_rows = max(5000, int(evaluation_max_rows))
        self.planner = Planner()
        self.observer = Observer()
        self.enable_unit_scale = self._env_flag("AGENTIC_ENABLE_UNIT_SCALE", "1")
        self.enable_axis_invert = self._env_flag("AGENTIC_ENABLE_AXIS_INVERT", "1")
        self.enable_smoothing = self._env_flag("AGENTIC_ENABLE_SMOOTHING", "1")
        self.smoothing_noise_ratio = float(os.getenv("AGENTIC_SMOOTHING_NOISE_RATIO", "1.35"))
        self.smoothing_window = max(3, int(os.getenv("AGENTIC_SMOOTHING_WINDOW", "5")))
        self.smoothing_max_columns = max(1, int(os.getenv("AGENTIC_SMOOTHING_MAX_COLUMNS", "6")))

    def _env_flag(self, key: str, default: str = "0") -> bool:
        value = str(os.getenv(key, default)).strip().lower()
        return value in {"1", "true", "yes", "on"}

    def _sample_for_observer(self, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) <= self.evaluation_max_rows:
            return df
        step = int(np.ceil(len(df) / float(self.evaluation_max_rows)))
        step = max(1, step)
        return df.iloc[::step].copy()

    def _orientation_score(self, df: pd.DataFrame) -> float:
        cols = [col for col in ("acc_x", "acc_y", "acc_z") if col in df.columns]
        if len(cols) < 3:
            return 0.7

        means = {}
        for col in cols:
            series = pd.to_numeric(df[col], errors="coerce")
            if series.notna().sum() < 10:
                return 0.7
            means[col] = float(series.mean())

        dominant = max(means, key=lambda name: abs(means[name]))
        dom_mean = float(means[dominant])
        if abs(dom_mean) < 0.5:
            return 0.7
        if dominant == "acc_z" and dom_mean > 0:
            return 1.0
        if dom_mean < 0:
            return 0.35
        return 0.75

    def _noise_score(self, df: pd.DataFrame) -> float:
        cols = [
            col
            for col in (
                "acc_x",
                "acc_y",
                "acc_z",
                "gyro_x",
                "gyro_y",
                "gyro_z",
                "mag_x",
                "mag_y",
                "mag_z",
                "heart_rate",
                "pressure",
                "light_lux",
                "gps_speed",
            )
            if col in df.columns
        ]
        if not cols:
            return 0.7

        ratios: list[float] = []
        for col in cols:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(series) < 20:
                continue
            signal_std = float(series.std(ddof=0))
            if signal_std <= 1e-9:
                continue
            diff_std = float(series.diff().dropna().std(ddof=0))
            ratios.append(diff_std / (signal_std + 1e-9))

        if not ratios:
            return 0.7
        median_ratio = float(np.median(ratios))
        return float(max(0.0, min(1.0, 1.0 / (1.0 + median_ratio))))

    def _dataset_policy_score(self, df: pd.DataFrame) -> float:
        sampled = self._sample_for_observer(df)
        # Align acceptance objective with production HQScore v4 as closely as possible.
        score = self._hqscore_v4_single(sampled)
        return float(max(0.0, min(1.0, score)))

    def _estimate_rate_hz(self, df: pd.DataFrame) -> float:
        if "timestamp" not in df.columns:
            return 1.0
        ts = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed")
        diffs = ts.diff().dt.total_seconds().dropna()
        if len(diffs) == 0:
            return 1.0
        median = float(diffs.median())
        if median <= 0:
            return 1.0
        return float(1.0 / median)

    def _hqscore_v4_single(self, df: pd.DataFrame) -> float:
        try:
            rate_hz = self._estimate_rate_hz(df)
            payload = compute_hqscore_v4(
                merged_df=df,
                resampled=[df],
                sampling_rate_hz=rate_hz,
                drift_analysis={"stability_score": 1.0, "dtw_score": 0.0, "drift_type": "none"},
                task_inference=None,
                disable_advanced=False,
                limited_modality=False,
            )
            return float(payload.get("overall", 0.0))
        except Exception:
            # Preserve robustness: fallback if any feature subset fails.
            return float(self.observer.evaluate(df))

    def _state_score(self, datasets: list[pd.DataFrame]) -> float:
        if not datasets:
            return 0.0

        scores = [self._dataset_policy_score(df) for df in datasets]
        return float(np.mean(scores)) if scores else 0.0

    def _propose_actions(self, datasets: list[pd.DataFrame]) -> list[AgentAction]:
        actions: list[AgentAction] = []

        for idx, df in enumerate(datasets):
            dataset_name = f"dataset{idx + 1}"
            if self.enable_unit_scale:
                conflicts = self.planner.detect_conflicts(df)
                for conflict in conflicts:
                    action = str(conflict.get("action", ""))
                    if action != "scale_all_acc":
                        continue

                    factor = float(conflict.get("factor", 1.0))
                    if abs(factor - 1.0) < 1e-9:
                        continue

                    acc_cols = [col for col in ("acc_x", "acc_y", "acc_z") if col in df.columns]
                    if not acc_cols:
                        continue

                    actions.append(
                        AgentAction(
                            action_id=f"scale_acc_{dataset_name}_{round(factor, 5)}",
                            dataset_index=idx,
                            type="scale_many",
                            parameters={"columns": acc_cols, "factor": factor},
                            rationale=f"Detected accelerometer unit mismatch ({dataset_name}).",
                            source=str(conflict.get("type", "unit_auto_detect")),
                        )
                    )

            if self.enable_axis_invert:
                actions.extend(self._propose_axis_inversion_actions(df, idx))

            if self.enable_smoothing:
                actions.extend(self._propose_smoothing_actions(df, idx))

        return actions

    def _propose_axis_inversion_actions(self, df: pd.DataFrame, dataset_index: int) -> list[AgentAction]:
        actions: list[AgentAction] = []
        dataset_name = f"dataset{dataset_index + 1}"
        families = (
            ("acc", ("acc_x", "acc_y", "acc_z"), 0.5),
            ("gyro", ("gyro_x", "gyro_y", "gyro_z"), 0.05),
            ("mag", ("mag_x", "mag_y", "mag_z"), 1.0),
        )

        for family_name, columns, threshold in families:
            available = [col for col in columns if col in df.columns]
            if len(available) < 3:
                continue

            means: dict[str, float] = {}
            for col in available:
                series = pd.to_numeric(df[col], errors="coerce")
                if series.notna().sum() < 10:
                    continue
                means[col] = float(series.mean())

            if len(means) < 3:
                continue

            dominant_col = max(means, key=lambda name: abs(means[name]))
            dominant_mean = float(means[dominant_col])
            if dominant_mean >= 0 or abs(dominant_mean) < threshold:
                continue

            actions.append(
                AgentAction(
                    action_id=f"invert_{dataset_name}_{dominant_col}",
                    dataset_index=dataset_index,
                    type="invert_many",
                    parameters={"columns": [dominant_col]},
                    rationale=(
                        f"{family_name.upper()} dominant axis {dominant_col} has strong negative bias "
                        f"({dominant_mean:.3f}); test sign inversion."
                    ),
                    source="heuristic_axis_sign",
                )
            )

        return actions

    def _propose_smoothing_actions(self, df: pd.DataFrame, dataset_index: int) -> list[AgentAction]:
        candidate_columns = [
            col
            for col in (
                "acc_x",
                "acc_y",
                "acc_z",
                "gyro_x",
                "gyro_y",
                "gyro_z",
                "mag_x",
                "mag_y",
                "mag_z",
                "heart_rate",
                "pressure",
                "light_lux",
                "gps_speed",
            )
            if col in df.columns
        ]
        noisy_ranked: list[tuple[float, str]] = []

        for col in candidate_columns:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(series) < 50:
                continue

            signal_std = float(series.std(ddof=0))
            if signal_std <= 1e-9:
                continue
            diff_std = float(series.diff().dropna().std(ddof=0))
            noise_ratio = diff_std / (signal_std + 1e-9)

            if noise_ratio >= self.smoothing_noise_ratio:
                noisy_ranked.append((noise_ratio, col))

        if not noisy_ranked:
            return []

        noisy_ranked.sort(reverse=True)
        selected_cols = [col for _, col in noisy_ranked[: self.smoothing_max_columns]]
        avg_noise = float(np.mean([ratio for ratio, _ in noisy_ranked[: self.smoothing_max_columns]]))
        dataset_name = f"dataset{dataset_index + 1}"

        return [
            AgentAction(
                action_id=f"smooth_{dataset_name}_{'_'.join(selected_cols[:2])}_{self.smoothing_window}",
                dataset_index=dataset_index,
                type="smooth_many",
                parameters={"columns": selected_cols, "window": self.smoothing_window},
                rationale=(
                    f"Detected high-frequency noise ratio ~{avg_noise:.2f} in {len(selected_cols)} "
                    f"columns; test median smoothing."
                ),
                source="heuristic_noise_reduction",
            )
        ]

    def _apply_action(
        self,
        datasets: list[pd.DataFrame],
        action: AgentAction,
    ) -> tuple[list[pd.DataFrame], int]:
        mutated = [frame.copy() for frame in datasets]
        target_df = mutated[action.dataset_index]
        executor = TransformationExecutor()

        if action.type == "scale_many":
            factor = float(action.parameters.get("factor", 1.0))
            columns = [str(col) for col in action.parameters.get("columns", [])]
            for column in columns:
                if column not in target_df.columns:
                    continue
                if not pd.api.types.is_numeric_dtype(target_df[column]):
                    coerced = pd.to_numeric(target_df[column], errors="coerce")
                    if coerced.notna().sum() == 0:
                        continue
                    target_df[column] = coerced
                target_df, _ = executor.apply(
                    target_df,
                    "scale",
                    {"column": column, "factor": factor},
                )
            mutated[action.dataset_index] = target_df
        elif action.type == "invert_many":
            columns = [str(col) for col in action.parameters.get("columns", [])]
            for column in columns:
                if column not in target_df.columns:
                    continue
                if not pd.api.types.is_numeric_dtype(target_df[column]):
                    coerced = pd.to_numeric(target_df[column], errors="coerce")
                    if coerced.notna().sum() == 0:
                        continue
                    target_df[column] = coerced
                target_df, _ = executor.apply(
                    target_df,
                    "invert",
                    {"column": column},
                )
            mutated[action.dataset_index] = target_df
        elif action.type == "smooth_many":
            columns = [str(col) for col in action.parameters.get("columns", [])]
            window = int(action.parameters.get("window", self.smoothing_window))
            for column in columns:
                if column not in target_df.columns:
                    continue
                if not pd.api.types.is_numeric_dtype(target_df[column]):
                    coerced = pd.to_numeric(target_df[column], errors="coerce")
                    if coerced.notna().sum() == 0:
                        continue
                    target_df[column] = coerced
                target_df, _ = executor.apply(
                    target_df,
                    "smooth",
                    {"column": column, "window": window},
                )
            mutated[action.dataset_index] = target_df
        else:
            raise ValueError(f"Unsupported agent action type: {action.type}")

        return mutated, len(executor.history)

    def run(self, datasets: list[pd.DataFrame]) -> tuple[list[pd.DataFrame], dict[str, Any]]:
        current = [frame.copy() for frame in datasets]
        initial_score = self._state_score(current)
        current_score = initial_score

        accepted_actions: list[dict[str, Any]] = []
        rejected_actions: list[dict[str, Any]] = []
        tried_action_ids: set[str] = set()
        stop_reason = "no_actions"

        for iteration in range(1, self.max_iterations + 1):
            candidates = [action for action in self._propose_actions(current) if action.action_id not in tried_action_ids]
            if not candidates:
                stop_reason = "no_new_actions"
                break

            best_payload: dict[str, Any] | None = None
            best_score = current_score
            best_state: list[pd.DataFrame] | None = None

            for action in candidates:
                tried_action_ids.add(action.action_id)
                candidate_state, executor_steps = self._apply_action(current, action)
                candidate_score = self._state_score(candidate_state)
                improvement = float(candidate_score - current_score)

                candidate_payload = {
                    "iteration": iteration,
                    "action_id": action.action_id,
                    "dataset_id": f"dataset{action.dataset_index + 1}",
                    "action_type": action.type,
                    "source": action.source,
                    "rationale": action.rationale,
                    "score_before": round(current_score, 4),
                    "score_after": round(candidate_score, 4),
                    "improvement": round(improvement, 4),
                    "executor_steps": int(executor_steps),
                }

                if improvement > (best_score - current_score):
                    best_payload = candidate_payload
                    best_score = candidate_score
                    best_state = candidate_state
                else:
                    rejected_actions.append(candidate_payload)

            if best_payload is None or best_state is None:
                stop_reason = "no_viable_candidates"
                break

            net_improvement = float(best_score - current_score)
            if net_improvement < self.min_improvement:
                stop_reason = "no_action_above_improvement_threshold"
                rejected_actions.append(best_payload)
                break

            confidence = float(self.observer.compute_confidence(current_score, best_score))
            best_payload["observer_confidence"] = round(confidence, 4)
            accepted_actions.append(best_payload)

            current = best_state
            current_score = float(best_score)
            stop_reason = "max_iterations_reached"

        final_score = self._state_score(current)
        used = len(accepted_actions) > 0

        report = {
            "enabled": True,
            "used": used,
            "policy": "greedy_safe_search_v1",
            "iterations": len(accepted_actions),
            "initial_quality_score": round(initial_score, 4),
            "final_quality_score": round(final_score, 4),
            "net_improvement": round(final_score - initial_score, 4),
            "confidence": round(float(self.observer.compute_confidence(initial_score, final_score)), 4),
            "accepted_actions": accepted_actions,
            "rejected_actions": rejected_actions[:20],
            "stop_reason": stop_reason,
        }

        return current, report
