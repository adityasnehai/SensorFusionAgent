from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class BenchmarkScenario:
    name: str
    path: Path
    datasets: list[pd.DataFrame]
    metadata: dict[str, Any]


def _read_dataframe(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed")
        df = df.dropna(subset=["timestamp"])
    return df


def load_scenarios(datasets_dir: str | Path) -> list[BenchmarkScenario]:
    root = Path(datasets_dir)
    if not root.exists():
        return []

    scenarios: list[BenchmarkScenario] = []

    for scenario_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        csv_files = sorted(scenario_dir.glob("dataset*.csv"))
        if len(csv_files) < 2:
            continue

        datasets = [_read_dataframe(path) for path in csv_files]

        metadata_path = scenario_dir / "metadata.json"
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if not isinstance(metadata, dict):
                    metadata = {}
            except Exception:
                metadata = {}

        scenarios.append(
            BenchmarkScenario(
                name=scenario_dir.name,
                path=scenario_dir,
                datasets=datasets,
                metadata=metadata,
            )
        )

    return scenarios
