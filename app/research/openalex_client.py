from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests


OPENALEX_WORKS_URL = "https://api.openalex.org/works"
LOGGER = logging.getLogger(__name__)


def _decode_abstract(inverted_index: Dict[str, List[int]] | None) -> str:
    if not inverted_index:
        return ""

    words_by_pos: Dict[int, str] = {}
    for token, positions in inverted_index.items():
        for pos in positions:
            words_by_pos[pos] = token

    ordered = [words_by_pos[i] for i in sorted(words_by_pos.keys()) if i in words_by_pos]
    return " ".join(ordered)


def _extract_source_name(work: Dict[str, Any]) -> str:
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    return source.get("display_name") or "Unknown source"


def search_openalex(query: str, per_page: int = 5) -> List[Dict[str, Any]]:
    """Search OpenAlex works and return normalized top papers.

    OpenAlex response shape:
    {
      "results": [
        {
          "display_name": "...",
          "cited_by_count": 123,
          "publication_year": 2016,
          "primary_location": {"source": {"display_name": "Journal"}}
        }
      ]
    }
    """
    params = {
        "search": query,
        "per-page": per_page,
        "select": "id,title,display_name,publication_year,cited_by_count,primary_location,abstract_inverted_index",
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "SensorFusionAgent/1.0 (research-suggestions)",
    }

    try:
        response = requests.get(OPENALEX_WORKS_URL, params=params, headers=headers, timeout=12)
        response.raise_for_status()
        payload = response.json()
        LOGGER.info("OpenAlex query=%s status=%s", query, response.status_code)
        LOGGER.debug("OpenAlex raw payload: %s", payload)
    except Exception as exc:
        LOGGER.warning("OpenAlex request failed for query '%s': %s", query, exc)
        return []

    parsed: List[Dict[str, Any]] = []
    for work in payload.get("results", []):
        abstract_text = _decode_abstract(work.get("abstract_inverted_index"))
        citation_count = int(work.get("cited_by_count") or 0)
        parsed.append(
            {
                "title": work.get("display_name") or work.get("title") or "Untitled work",
                "year": work.get("publication_year"),
                "citation_count": citation_count,
                "source": _extract_source_name(work),
                "url": work.get("id"),
                "abstract_snippet": abstract_text[:400] if abstract_text else None,
            }
        )

    parsed.sort(key=lambda paper: int(paper.get("citation_count") or 0), reverse=True)
    return parsed[:per_page]
