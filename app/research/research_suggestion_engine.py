from __future__ import annotations

import re
from typing import Dict, List

import pandas as pd

from app.core.modality_registry import MODALITY_REGISTRY
from app.research.openalex_client import search_openalex


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

    return round(float(1.0 / median), 2)


def _detect_modalities(df: pd.DataFrame) -> List[str]:
    found: List[str] = []
    for modality, config in MODALITY_REGISTRY.items():
        if any(col in df.columns for col in config["columns"]):
            found.append(modality)
    return found


def _infer_task(modalities: List[str], sampling_rates: List[float]) -> str:
    has_imu = "accelerometer" in modalities and "gyroscope" in modalities
    has_gps = "gps" in modalities
    avg_rate = sum(sampling_rates) / len(sampling_rates) if sampling_rates else 0

    if has_imu and 20 <= avg_rate <= 100:
        return "human_activity_recognition"
    if has_gps:
        return "locomotion"
    return "generic_imu"


def _normalize_task_label(task_label: str) -> str:
    normalized = str(task_label or "").strip().lower()
    mapping = {
        "human activity recognition": "human_activity_recognition",
        "gait analysis": "gait_analysis",
        "free-living monitoring": "free_living_monitoring",
        "driving behavior": "driving_behavior",
        "health monitoring": "health_monitoring",
        "environmental sensing": "environmental_sensing",
    }
    return mapping.get(normalized, normalized.replace(" ", "_"))


def _build_query(modalities: List[str], task: str) -> str:
    modality_phrase = " ".join(sorted(set(modalities))) if modalities else "sensor"
    if task == "human_activity_recognition":
        task_phrase = "human activity recognition"
    elif task == "gait_analysis":
        task_phrase = "gait analysis"
    elif task == "driving_behavior":
        task_phrase = "driving behavior"
    elif task == "health_monitoring":
        task_phrase = "health monitoring"
    elif task == "environmental_sensing":
        task_phrase = "environmental sensing"
    elif task == "free_living_monitoring":
        task_phrase = "free living monitoring"
    elif task == "locomotion":
        task_phrase = "locomotion tracking"
    else:
        task_phrase = "imu analysis"
    return f"smartphone {modality_phrase} dataset sampling rate {task_phrase}"


def _build_query_candidates(modalities: List[str], task: str) -> List[str]:
    modality_phrase = " ".join(sorted(set(modalities))) if modalities else "imu sensor"
    task_phrase = task.replace("_", " ")

    candidates = [
        _build_query(modalities, task),
        f"{modality_phrase} {task_phrase} sampling rate dataset",
        f"{modality_phrase} sensor fusion time series alignment",
        f"{modality_phrase} wearable dataset harmonization",
        "human activity recognition accelerometer gyroscope sampling rate",
        "sensor harmonization resampling strategy time series",
    ]

    unique: List[str] = []
    seen = set()
    for candidate in candidates:
        normalized = " ".join(candidate.split()).strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(candidate)
    return unique


def _collect_top_papers(queries: List[str], top_n: int = 5) -> tuple[List[dict], str]:
    merged: Dict[str, dict] = {}
    selected_query = queries[0] if queries else ""

    for query in queries:
        papers = search_openalex(query, per_page=20)
        if papers and not merged:
            selected_query = query

        for paper in papers:
            key = str(paper.get("url") or paper.get("title") or "").strip().lower()
            if not key:
                continue

            existing = merged.get(key)
            if not existing or int(paper.get("citation_count") or 0) > int(existing.get("citation_count") or 0):
                merged[key] = paper

        if len(merged) >= 12:
            break

    ranked = sorted(
        merged.values(),
        key=lambda paper: int(paper.get("citation_count") or 0),
        reverse=True,
    )
    return ranked[:top_n], selected_query


def _extract_sampling_rate_from_text(text: str) -> List[int]:
    values = []
    for match in re.findall(r"\b(\d{1,3})\s*hz\b", text.lower()):
        hz = int(match)
        if 5 <= hz <= 400:
            values.append(hz)
    return values


def _derive_recommendation(task: str, papers: List[dict], fallback_rates: List[float]) -> dict:
    snippets = " ".join(filter(None, [paper.get("abstract_snippet") or "" for paper in papers]))
    sampled_rates = _extract_sampling_rate_from_text(snippets)

    recommended_rate: int | None
    if sampled_rates:
        sampled_rates.sort()
        recommended_rate = sampled_rates[len(sampled_rates) // 2]
    elif papers:
        if task == "human_activity_recognition":
            recommended_rate = 50
        elif task == "locomotion":
            recommended_rate = 25
        else:
            fallback = [r for r in fallback_rates if r > 0]
            recommended_rate = int(round(sum(fallback) / len(fallback))) if fallback else 50
    else:
        recommended_rate = None

    confidence = 0.2
    if papers:
        citation_strength = sum(min(1.0, (paper.get("citation_count", 0) / 1500.0)) for paper in papers)
        confidence += min(0.75, citation_strength / max(1, len(papers)) * 0.75)
    confidence = round(min(0.95, confidence), 2)

    return {
        "recommended_sampling_rate": recommended_rate,
        "confidence": confidence,
    }


def _default_suggestion(task: str, modalities: List[str], query: str) -> dict:
    return {
        "recommended_sampling_rate": None,
        "confidence": 0.0,
        "papers": [],
        "summary": "No relevant research found.",
        "inferred_task": task,
        "detected_modalities": modalities,
        "query": query,
        "window_size_seconds": None,
        "resampling_strategy": None,
        "common_sensor_combinations": [],
    }


def generate_research_suggestion(
    dataframes: List[pd.DataFrame],
    task_context: dict | None = None,
) -> dict:
    modalities: List[str] = []
    sampling_rates: List[float] = []
    for df in dataframes:
        modalities.extend(_detect_modalities(df))
        sampling_rates.append(_estimate_sampling_rate(df))

    modalities = sorted(set(modalities))
    context_task = (
        _normalize_task_label(task_context.get("predicted_task"))
        if isinstance(task_context, dict)
        else ""
    )
    task = context_task or _infer_task(modalities, sampling_rates)
    query_candidates = _build_query_candidates(modalities, task)
    papers_raw, selected_query = _collect_top_papers(query_candidates, top_n=5)
    papers = [
        {
            "title": str(paper.get("title") or "Untitled"),
            "year": paper.get("year"),
            "citation_count": int(paper.get("citation_count") or 0),
            "source": str(paper.get("source") or "Unknown source"),
            "url": paper.get("url"),
            "abstract_snippet": paper.get("abstract_snippet"),
        }
        for paper in papers_raw
    ]

    papers.sort(key=lambda paper: paper["citation_count"], reverse=True)
    papers = papers[:5]

    if not papers:
        return _default_suggestion(task, modalities, selected_query)

    practices = _derive_recommendation(task, papers, sampling_rates)
    recommended_rate = practices["recommended_sampling_rate"]
    if recommended_rate is None and isinstance(task_context, dict):
        suggested_rate = task_context.get("suggested_sampling_rate_hz")
        if isinstance(suggested_rate, (int, float)) and suggested_rate > 0:
            recommended_rate = int(round(float(suggested_rate)))
    sensor_combo = " + ".join(modalities) if modalities else "sensor"

    rate_text = f"~{recommended_rate}Hz" if recommended_rate is not None else "a task-specific rate"
    summary = (
        f"Based on top-cited literature, {rate_text} is commonly used for "
        f"{task.replace('_', ' ')} with {sensor_combo} modalities."
    )

    return {
        "recommended_sampling_rate": recommended_rate,
        "confidence": practices["confidence"],
        "papers": papers,
        "summary": summary,
        "inferred_task": task,
        "detected_modalities": modalities,
        "query": selected_query,
        "window_size_seconds": (
            str(task_context.get("suggested_window_seconds"))
            if isinstance(task_context, dict) and task_context.get("suggested_window_seconds") is not None
            else None
        ),
        "resampling_strategy": (
            str(task_context.get("hqscore_weight_profile"))
            if isinstance(task_context, dict) and task_context.get("hqscore_weight_profile")
            else None
        ),
        "common_sensor_combinations": [sensor_combo] if sensor_combo else [],
    }
