#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.runner import BenchmarkConfig, BenchmarkRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SensorFusionAgent benchmark evaluation framework")
    parser.add_argument("--datasets-dir", default="benchmarks/datasets", help="Directory containing benchmark scenarios")
    parser.add_argument("--results-dir", default="benchmarks/results", help="Directory for JSON/CSV benchmark outputs")
    parser.add_argument(
        "--max-alignment-error-seconds",
        type=float,
        default=1.0,
        help="Normalization reference for alignment MAE",
    )
    parser.add_argument(
        "--drift-variance-reference",
        type=float,
        default=0.0025,
        help="Variance reference for drift stability normalization",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    config = BenchmarkConfig(
        datasets_dir=Path(args.datasets_dir),
        results_dir=Path(args.results_dir),
        max_alignment_error_seconds=float(args.max_alignment_error_seconds),
        drift_variance_reference=float(args.drift_variance_reference),
    )

    runner = BenchmarkRunner(config)
    payload = runner.run()

    aggregate = payload.get("aggregate", {})
    print(
        json.dumps(
            {
                "scenarios_evaluated": aggregate.get("scenarios_evaluated", 0),
                "mean_signal_score": aggregate.get("mean_signal_score", 0.0),
                "mean_agent_score": aggregate.get("mean_agent_score", 0.0),
                "mean_final_score": aggregate.get("mean_final_score", 0.0),
                "results_json": str(config.results_dir / "benchmark_results.json"),
                "results_csv": str(config.results_dir / "benchmark_summary.csv"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
