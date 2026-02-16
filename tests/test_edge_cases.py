from __future__ import annotations

import pandas as pd
import pytest

from app.agent.loop import HarmonizationLoop
from app.core.exceptions import FusionPipelineError
from app.ingestion import structure_intelligence as si


def _write_csv(path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def test_empty_dataset_returns_dataset_empty(tmp_path):
    slot = tmp_path / "dataset1"
    slot.mkdir(parents=True)
    (slot / "empty.csv").write_text("timestamp,acc_x\n", encoding="utf-8")

    with pytest.raises(FusionPipelineError) as exc:
        si.build_slot_bundle("dataset1", str(slot))

    assert exc.value.error_type == "dataset_empty"
    assert "empty" in exc.value.message.lower()


def test_corrupted_csv_returns_invalid_csv(tmp_path):
    slot = tmp_path / "dataset1"
    slot.mkdir(parents=True)
    # Unclosed quote triggers parser error in pandas.
    (slot / "broken.csv").write_text('timestamp,acc_x\n"2024-01-01 00:00:00,1.0\n', encoding="utf-8")

    with pytest.raises(FusionPipelineError) as exc:
        si.build_slot_bundle("dataset1", str(slot))

    assert exc.value.error_type == "invalid_csv"


def test_no_overlap_returns_structured_error():
    loop = HarmonizationLoop()
    df1 = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01 00:00:00", periods=50, freq="100ms"),
            "acc_x": 1.0,
            "acc_y": 0.0,
            "acc_z": 0.0,
        }
    )
    df2 = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01 00:02:00", periods=50, freq="100ms"),
            "acc_x": 1.1,
            "acc_y": 0.1,
            "acc_z": 0.0,
        }
    )

    with pytest.raises(FusionPipelineError) as exc:
        loop.run([df1, df2])

    assert exc.value.error_type == "no_time_overlap"


def test_large_dataset_strict_limit_returns_dataset_too_large(tmp_path, monkeypatch):
    slot = tmp_path / "dataset1"
    slot.mkdir(parents=True)

    rows = [
        {"timestamp": f"2024-01-01 00:00:{i:02d}", "acc_x": float(i), "acc_y": 0.0, "acc_z": 0.0}
        for i in range(30)
    ]
    _write_csv(slot / "large.csv", rows)

    monkeypatch.setattr(si, "MAX_DATASET_ROWS", 10)
    monkeypatch.setattr(si, "STRICT_MAX_ROWS", True)

    with pytest.raises(FusionPipelineError) as exc:
        si.build_slot_bundle("dataset1", str(slot))

    assert exc.value.error_type == "dataset_too_large"


def test_single_modality_completes_with_warning():
    loop = HarmonizationLoop()
    ts = pd.date_range("2024-01-01 00:00:00", periods=120, freq="100ms")
    df1 = pd.DataFrame({"timestamp": ts, "acc_x": 1.0})
    df2 = pd.DataFrame({"timestamp": ts, "acc_x": 1.2})

    _, _, _, fusion_report, _, _ = loop.run([df1, df2])

    warnings = fusion_report.get("warnings") or []
    assert any("Limited modality available." == warning for warning in warnings)
