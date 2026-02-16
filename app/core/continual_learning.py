from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from app.core.modality_registry import MODALITY_REGISTRY

LOGGER = logging.getLogger(__name__)

TASK_LABELS = [
    "Human Activity Recognition",
    "Gait Analysis",
    "Free-living Monitoring",
    "Driving Behavior",
    "Health Monitoring",
    "Environmental Sensing",
    "Unknown",
]


class ContinualLearningManager:
    """Maintains lightweight continual-learning models for adaptive harmonization decisions."""

    def __init__(self) -> None:
        model_dir = Path(os.getenv("ADAPTIVE_MODEL_DIR", "models/adaptive"))
        model_dir.mkdir(parents=True, exist_ok=True)

        self.model_path = model_dir / "adaptive_model.joblib"
        self.state_path = model_dir / "adaptive_state.json"

        self.train_every_n = max(1, int(os.getenv("ADAPTIVE_TRAIN_EVERY_N", "20")))
        self.min_samples = max(8, int(os.getenv("ADAPTIVE_MIN_SAMPLES", "20")))
        self.use_threshold = float(os.getenv("ADAPTIVE_CONFIDENCE_THRESHOLD", "0.7"))

    @property
    def feature_names(self) -> list[str]:
        modality_features = [f"modality::{modality}" for modality in sorted(MODALITY_REGISTRY.keys())]
        task_features = [f"task::{task}" for task in TASK_LABELS]
        scalar_features = [
            "sampling_rate_mean",
            "sampling_rate_min",
            "sampling_rate_max",
            "sampling_rate_std",
            "duration_seconds",
            "drift_flag",
            "user_override_flag",
        ]
        return modality_features + task_features + scalar_features

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except Exception:
            return default
        if not np.isfinite(number):
            return default
        return number

    def extract_features(self, context: dict[str, Any]) -> np.ndarray:
        modalities = {str(m) for m in context.get("modalities", [])}
        sampling_rates = [self._safe_float(v) for v in context.get("sampling_rates_hz", [])]
        sampling_rates = [v for v in sampling_rates if v > 0]

        if sampling_rates:
            rate_mean = float(np.mean(sampling_rates))
            rate_min = float(np.min(sampling_rates))
            rate_max = float(np.max(sampling_rates))
            rate_std = float(np.std(sampling_rates))
        else:
            rate_mean = rate_min = rate_max = rate_std = 0.0

        task_label = str(context.get("task_type", "Unknown"))

        vector: list[float] = []
        for modality in sorted(MODALITY_REGISTRY.keys()):
            vector.append(1.0 if modality in modalities else 0.0)

        for task in TASK_LABELS:
            vector.append(1.0 if task_label == task else 0.0)

        vector.extend(
            [
                rate_mean,
                rate_min,
                rate_max,
                rate_std,
                self._safe_float(context.get("duration_seconds", 0.0), 0.0),
                1.0 if bool(context.get("drift_flag", False)) else 0.0,
                1.0 if bool(context.get("user_override_flag", False)) else 0.0,
            ]
        )

        return np.array(vector, dtype=float)

    def _load_bundle(self) -> dict[str, Any] | None:
        if not self.model_path.exists():
            return None
        try:
            return joblib.load(self.model_path)
        except Exception as exc:
            LOGGER.warning("Failed to load adaptive model: %s", exc)
            return None

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {
                "model_version": "untrained",
                "last_train_sample_count": 0,
                "train_mae_rate": None,
                "train_mae_hqscore": None,
                "trained_at": None,
            }
        try:
            with self.state_path.open("r", encoding="utf-8") as fp:
                loaded = json.load(fp)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass
        return {
            "model_version": "untrained",
            "last_train_sample_count": 0,
            "train_mae_rate": None,
            "train_mae_hqscore": None,
            "trained_at": None,
        }

    def _persist_state(self, state: dict[str, Any]) -> None:
        with self.state_path.open("w", encoding="utf-8") as fp:
            json.dump(state, fp, indent=2)

    def _confidence_from_state(self, state: dict[str, Any], sample_count: int) -> float:
        mae_rate = self._safe_float(state.get("train_mae_rate"), 99.0)
        mae_hq = self._safe_float(state.get("train_mae_hqscore"), 99.0)

        rate_score = float(max(0.0, 1.0 - min(1.0, mae_rate / 20.0)))
        hq_score = float(max(0.0, 1.0 - min(1.0, mae_hq / 0.25)))
        sample_score = float(min(1.0, sample_count / 120.0))

        confidence = 0.4 * rate_score + 0.3 * hq_score + 0.3 * sample_score
        return float(max(0.0, min(1.0, confidence)))

    def get_performance_trend(self, session, limit: int = 30) -> list[dict[str, float]]:
        from app.core.database import Job

        rows = (
            session.query(Job)
            .filter(Job.status == "completed", Job.learning_metadata_json.isnot(None))
            .order_by(Job.created_at.asc())
            .all()
        )

        hqscores: list[float] = []
        for row in rows:
            try:
                payload = json.loads(row.learning_metadata_json)
            except Exception:
                continue
            score = self._safe_float(payload.get("hqscore"), -1.0)
            if 0.0 <= score <= 1.0:
                hqscores.append(score)

        if not hqscores:
            return []

        trend: list[dict[str, float]] = []
        window = 5
        for idx, score in enumerate(hqscores, start=1):
            left = max(0, idx - window)
            subset = hqscores[left:idx]
            moving = float(np.mean(subset)) if subset else float(score)
            trend.append(
                {
                    "job_index": float(idx),
                    "hqscore": round(float(score), 4),
                    "moving_avg": round(moving, 4),
                }
            )

        return trend[-limit:]

    def recommend(self, session, context: dict[str, Any]) -> dict[str, Any]:
        state = self._load_state()
        bundle = self._load_bundle()
        trend = self.get_performance_trend(session)

        response = {
            "used": False,
            "confidence": 0.0,
            "model_version": state.get("model_version", "untrained"),
            "predicted_sampling_rate_hz": None,
            "expected_hqscore": None,
            "performance_trend": trend,
        }

        if not bundle:
            return response

        rate_model = bundle.get("rate_model")
        hq_model = bundle.get("hq_model")
        if rate_model is None or hq_model is None:
            return response

        x = self.extract_features(context).reshape(1, -1)

        try:
            predicted_rate = self._safe_float(rate_model.predict(x)[0], 0.0)
            expected_hqscore = self._safe_float(hq_model.predict(x)[0], 0.0)
        except Exception as exc:
            LOGGER.warning("Adaptive model prediction failed: %s", exc)
            return response

        confidence = self._confidence_from_state(
            state,
            int(self._safe_float(state.get("last_train_sample_count", 0), 0.0)),
        )

        response.update(
            {
                "confidence": round(confidence, 4),
                "predicted_sampling_rate_hz": round(predicted_rate, 4) if predicted_rate > 0 else None,
                "expected_hqscore": round(float(max(0.0, min(1.0, expected_hqscore))), 4),
            }
        )

        if response["predicted_sampling_rate_hz"] and confidence >= self.use_threshold:
            response["used"] = True
            LOGGER.info(
                "Adaptive decision accepted: predicted_rate=%.3fHz confidence=%.3f model=%s",
                float(response["predicted_sampling_rate_hz"]),
                confidence,
                response["model_version"],
            )
        else:
            LOGGER.info(
                "Adaptive decision skipped: confidence=%.3f threshold=%.3f model=%s",
                confidence,
                self.use_threshold,
                response["model_version"],
            )

        return response

    def _load_training_records(self, session) -> list[dict[str, Any]]:
        from app.core.database import Job

        rows = (
            session.query(Job)
            .filter(Job.status == "completed", Job.learning_metadata_json.isnot(None))
            .order_by(Job.created_at.asc())
            .all()
        )

        records: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row.learning_metadata_json)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue

            rate = self._safe_float(payload.get("chosen_master_rate_hz"), -1.0)
            score = self._safe_float(payload.get("hqscore"), -1.0)
            if rate <= 0 or not (0.0 <= score <= 1.0):
                continue

            records.append(payload)

        return records

    def maybe_train(self, session) -> dict[str, Any]:
        records = self._load_training_records(session)
        sample_count = len(records)
        state = self._load_state()

        if sample_count < self.min_samples:
            return {
                "trained": False,
                "reason": f"not_enough_samples:{sample_count}",
                "model_version": state.get("model_version", "untrained"),
            }

        last_count = int(self._safe_float(state.get("last_train_sample_count", 0), 0.0))
        if (sample_count - last_count) < self.train_every_n:
            return {
                "trained": False,
                "reason": f"waiting_for_more_samples:{sample_count-last_count}",
                "model_version": state.get("model_version", "untrained"),
            }

        X = np.vstack([self.extract_features(record) for record in records])
        y_rate = np.array([self._safe_float(record.get("chosen_master_rate_hz"), 1.0) for record in records], dtype=float)
        y_hq = np.array([self._safe_float(record.get("hqscore"), 0.0) for record in records], dtype=float)

        if len(np.unique(y_rate)) <= 1:
            rate_model = DummyRegressor(strategy="constant", constant=float(np.mean(y_rate)))
        else:
            rate_model = GradientBoostingRegressor(random_state=42, n_estimators=140, max_depth=3)

        if len(np.unique(y_hq)) <= 1:
            hq_model = DummyRegressor(strategy="constant", constant=float(np.mean(y_hq)))
        else:
            hq_model = GradientBoostingRegressor(random_state=42, n_estimators=120, max_depth=3)

        rate_model.fit(X, y_rate)
        hq_model.fit(X, y_hq)

        pred_rate = rate_model.predict(X)
        pred_hq = hq_model.predict(X)

        mae_rate = float(mean_absolute_error(y_rate, pred_rate))
        mae_hq = float(mean_absolute_error(y_hq, pred_hq))

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        model_version = f"adaptive-{timestamp}"

        if self.model_path.exists():
            backup = self.model_path.with_suffix(f".joblib.bak.{timestamp}")
            try:
                self.model_path.replace(backup)
            except Exception:
                LOGGER.warning("Could not create adaptive model backup before update")

        bundle = {
            "rate_model": rate_model,
            "hq_model": hq_model,
            "feature_names": self.feature_names,
            "state": {
                "model_version": model_version,
                "last_train_sample_count": sample_count,
                "train_mae_rate": round(mae_rate, 6),
                "train_mae_hqscore": round(mae_hq, 6),
                "trained_at": datetime.utcnow().isoformat(),
            },
        }
        joblib.dump(bundle, self.model_path)

        state = bundle["state"]
        self._persist_state(state)

        LOGGER.info(
            "Adaptive model trained: version=%s samples=%s mae_rate=%.4f mae_hq=%.4f",
            model_version,
            sample_count,
            mae_rate,
            mae_hq,
        )

        return {
            "trained": True,
            "model_version": model_version,
            "sample_count": sample_count,
            "train_mae_rate": round(mae_rate, 6),
            "train_mae_hqscore": round(mae_hq, 6),
        }

    def persist_job_metadata(self, session, job_id: str, metadata: dict[str, Any]) -> None:
        from app.core.database import Job

        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.learning_metadata_json = json.dumps(metadata)
        session.commit()
