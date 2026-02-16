from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.core.continual_learning import ContinualLearningManager
from app.core.database import SessionLocal, init_db
from app.core.fusion_engine import FusionEngine

from benchmarks.dataset_loader import BenchmarkScenario, load_scenarios
from benchmarks.metrics import (
    compute_agent_metrics,
    compute_final_scores,
    compute_signal_metrics,
)
from benchmarks.policy import build_adaptive_context, choose_alignment_strategy


@dataclass
class BenchmarkConfig:
    datasets_dir: Path
    results_dir: Path
    max_alignment_error_seconds: float = 1.0
    drift_variance_reference: float = 0.0025


class BenchmarkRunner:
    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config
        self.fusion_engine = FusionEngine()
        self.cl_manager = ContinualLearningManager()

    def _read_model_versions(self) -> dict[str, str]:
        adaptive_version = "untrained"
        adaptive_state_path = Path("models/adaptive/adaptive_state.json")
        if adaptive_state_path.exists():
            try:
                payload = json.loads(adaptive_state_path.read_text(encoding="utf-8"))
                adaptive_version = str(payload.get("model_version", adaptive_version))
            except Exception:
                pass

        return {
            "adaptive_model_version": adaptive_version,
            "alignment_mode": "classical",
        }

    def _run_mode(
        self,
        datasets,
        *,
        alignment_mode: str,
        target_sampling_rate: float | None,
        task_inference: dict | None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        result = self.fusion_engine.fuse(
            datasets,
            target_sampling_rate=target_sampling_rate,
            task_inference=task_inference,
            alignment_mode=alignment_mode,
            schema_inference=None,
        )
        runtime = float(time.perf_counter() - start)

        return {
            "result": result,
            "runtime_seconds": runtime,
        }

    def _scenario_best_strategy(self, metadata: dict[str, Any], classical_hq: float) -> str:
        explicit = metadata.get("best_alignment_strategy")
        if isinstance(explicit, str) and explicit == "classical":
            return explicit
        return "classical"

    def _evaluate_scenario(self, scenario: BenchmarkScenario) -> dict[str, Any]:
        adaptive_context = build_adaptive_context(scenario.datasets)
        task_inference = adaptive_context.get("task_inference")
        policy = choose_alignment_strategy(scenario.datasets)

        classical_run = self._run_mode(
            scenario.datasets,
            alignment_mode="classical",
            target_sampling_rate=None,
            task_inference=task_inference,
        )

        session = SessionLocal()
        try:
            adaptive_choice = self.cl_manager.recommend(session, adaptive_context)
        finally:
            session.close()

        chosen_mode = str(policy["alignment_mode"])
        adaptive_rate = None
        if adaptive_choice.get("used") and adaptive_choice.get("predicted_sampling_rate_hz") is not None:
            adaptive_rate = float(adaptive_choice["predicted_sampling_rate_hz"])

        adaptive_run = self._run_mode(
            scenario.datasets,
            alignment_mode=chosen_mode,
            target_sampling_rate=adaptive_rate,
            task_inference=task_inference,
        )

        classical_result = classical_run["result"]
        adaptive_result = adaptive_run["result"]

        classical_signal = compute_signal_metrics(
            fusion_report=classical_result["fusion_report"],
            visual_data=classical_result["visual_data"],
            metadata=scenario.metadata,
            sampling_rate_hz=float(classical_result["rate"]),
            runtime_seconds=float(classical_run["runtime_seconds"]),
            drift_variance_reference=self.config.drift_variance_reference,
        )
        adaptive_signal = compute_signal_metrics(
            fusion_report=adaptive_result["fusion_report"],
            visual_data=adaptive_result["visual_data"],
            metadata=scenario.metadata,
            sampling_rate_hz=float(adaptive_result["rate"]),
            runtime_seconds=float(adaptive_run["runtime_seconds"]),
            drift_variance_reference=self.config.drift_variance_reference,
        )

        hqscore_without_agent = float(classical_result["score"])
        hqscore_with_agent = float(adaptive_result["score"])

        best_strategy = self._scenario_best_strategy(
            scenario.metadata,
            classical_hq=float(classical_result["score"]),
        )

        # Keep confidence source minimal and explicit:
        # adaptive model confidence blended with strategy confidence (if available).
        adaptive_conf = float(adaptive_choice.get("confidence", 0.0))
        strategy_conf = float(policy.get("strategy_confidence", 0.0))
        if adaptive_conf > 0 and strategy_conf > 0:
            predicted_confidence = float(np.mean([adaptive_conf, strategy_conf]))
        else:
            predicted_confidence = max(adaptive_conf, strategy_conf)

        agent_metrics = compute_agent_metrics(
            hqscore_with_agent=hqscore_with_agent,
            hqscore_without_agent=hqscore_without_agent,
            predicted_confidence=predicted_confidence,
            chosen_strategy=chosen_mode,
            best_strategy=best_strategy,
        )

        final_scores = compute_final_scores(
            signal_metrics=adaptive_signal,
            agent_metrics=agent_metrics,
            max_alignment_error_seconds=self.config.max_alignment_error_seconds,
        )

        return {
            "scenario": scenario.name,
            "metadata": scenario.metadata,
            "runs": {
                "classical": {
                    "alignment_mode": "classical",
                    "hqscore": round(float(classical_result["score"]), 6),
                    "sampling_rate": round(float(classical_result["rate"]), 6),
                    "signal_metrics": classical_signal,
                },
                "adaptive": {
                    "alignment_mode": chosen_mode,
                    "hqscore": round(float(adaptive_result["score"]), 6),
                    "sampling_rate": round(float(adaptive_result["rate"]), 6),
                    "signal_metrics": adaptive_signal,
                    "adaptive_decision": {
                        "used_sampling_override": bool(adaptive_rate is not None),
                        "predicted_sampling_rate_hz": adaptive_rate,
                        "adaptive_confidence": round(adaptive_conf, 6),
                        "strategy_confidence": round(strategy_conf, 6),
                        "reason": policy.get("reason"),
                    },
                },
            },
            "signal_metrics": adaptive_signal,
            "agent_metrics": agent_metrics,
            **final_scores,
            "agent_policy": {
                "chosen_strategy": chosen_mode,
                "best_strategy": best_strategy,
                "predicted_confidence": round(float(predicted_confidence), 6),
            },
        }

    def _write_outputs(self, payload: dict[str, Any]) -> None:
        self.config.results_dir.mkdir(parents=True, exist_ok=True)

        json_path = self.config.results_dir / "benchmark_results.json"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        csv_path = self.config.results_dir / "benchmark_summary.csv"
        rows = []
        for result in payload.get("scenarios", []):
            rows.append(
                {
                    "scenario": result.get("scenario"),
                    "final_score": result.get("final_score"),
                    "signal_score": result.get("signal_score"),
                    "agent_score": result.get("agent_score"),
                    "alignment_mae": (result.get("signal_metrics") or {}).get("alignment_mae"),
                    "wasserstein_similarity": (result.get("signal_metrics") or {}).get("wasserstein_similarity"),
                    "frequency_similarity": (result.get("signal_metrics") or {}).get("frequency_similarity"),
                    "drift_stability": (result.get("signal_metrics") or {}).get("drift_stability"),
                    "runtime_seconds": (result.get("signal_metrics") or {}).get("runtime_seconds"),
                    "hqscore_improvement": (result.get("agent_metrics") or {}).get("hqscore_improvement"),
                    "confidence_calibration_error": (result.get("agent_metrics") or {}).get("confidence_calibration_error"),
                    "strategy_selection_accuracy": (result.get("agent_metrics") or {}).get("strategy_selection_accuracy"),
                    "hqscore_classical": ((result.get("runs") or {}).get("classical") or {}).get("hqscore"),
                    "hqscore_adaptive": ((result.get("runs") or {}).get("adaptive") or {}).get("hqscore"),
                    "agent_chosen_strategy": ((result.get("agent_policy") or {}).get("chosen_strategy")),
                    "agent_best_strategy": ((result.get("agent_policy") or {}).get("best_strategy")),
                }
            )

        with csv_path.open("w", newline="", encoding="utf-8") as fp:
            if not rows:
                writer = csv.writer(fp)
                writer.writerow(["scenario", "final_score", "signal_score", "agent_score"])
            else:
                writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

    def run(self) -> dict[str, Any]:
        init_db()
        scenarios = load_scenarios(self.config.datasets_dir)

        results = [self._evaluate_scenario(scenario) for scenario in scenarios]

        signal_scores = [float(item.get("signal_score", 0.0)) for item in results]
        agent_scores = [float(item.get("agent_score", 0.0)) for item in results]
        final_scores = [float(item.get("final_score", 0.0)) for item in results]

        payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "model_versions": self._read_model_versions(),
            "benchmark_config": {
                "datasets_dir": str(self.config.datasets_dir),
                "results_dir": str(self.config.results_dir),
                "max_alignment_error_seconds": self.config.max_alignment_error_seconds,
                "drift_variance_reference": self.config.drift_variance_reference,
            },
            "aggregate": {
                "scenarios_evaluated": len(results),
                "mean_signal_score": round(float(np.mean(signal_scores)), 6) if signal_scores else 0.0,
                "mean_agent_score": round(float(np.mean(agent_scores)), 6) if agent_scores else 0.0,
                "mean_final_score": round(float(np.mean(final_scores)), 6) if final_scores else 0.0,
            },
            "scenarios": results,
        }

        self._write_outputs(payload)
        return payload
