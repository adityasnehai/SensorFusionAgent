from typing import List, Optional

from pydantic import BaseModel, Field


class ResearchPaper(BaseModel):
    title: str
    year: Optional[int] = None
    citation_count: int = 0
    source: str
    url: Optional[str] = None
    abstract_snippet: Optional[str] = None


class ResearchSuggestion(BaseModel):
    recommended_sampling_rate: Optional[int] = None
    confidence: float = Field(ge=0.0, le=1.0)
    papers: List[ResearchPaper]
    summary: str
    inferred_task: str
    detected_modalities: List[str]
    query: str
    window_size_seconds: Optional[str] = None
    resampling_strategy: Optional[str] = None
    common_sensor_combinations: List[str] = Field(default_factory=list)


class ResearchSuggestionStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    research_suggestion: Optional[ResearchSuggestion] = None
