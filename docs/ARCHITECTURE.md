# SensorFusionAgent Architecture

## System Overview

SensorFusionAgent is split into:
- Backend API and orchestration (`FastAPI`)
- Core fusion pipeline (`HarmonizationLoop`)
- Intelligence layers (schema/task/research/agentic/adaptive)
- Frontend dashboard (`Next.js`)

```mermaid
flowchart TD
  U[User Uploads Datasets] --> FE[Next.js Frontend]
  FE --> FUSE[POST /fuse]
  FUSE --> JOB[SQLite jobs table]
  FUSE --> BG[Background Task]

  BG --> ING[Ingestion + Structure Intelligence]
  ING --> TASK[Task Inference]
  TASK --> AGENT[Agentic Runtime]
  AGENT --> LOOP[Harmonization Loop]
  LOOP --> SCORE[HQScore v4 + Drift + Visual Data]
  SCORE --> RESEARCH[OpenAlex Research Suggestions]
  SCORE --> STORE[Persist result_json]
  STORE --> STATUS[GET /status/{job_id}]
  STATUS --> FE
```

## Backend Layers

### API Layer

Primary file:
- `app/api.py`

Responsibilities:
- Receives uploads and creates async jobs
- Stores job state/progress in DB
- Runs background fusion tasks
- Serves job status and downloads
- Handles structured error contracts

Endpoints:
- `POST /fuse`
- `GET /status/{job_id}`
- `GET /research_suggestions/{job_id}`
- `POST /research_suggestions/{job_id}/apply`
- `GET /download/{job_id}`

### Data and Job Persistence

Primary file:
- `app/core/database.py`

Stores:
- Job id/status/progress
- Result JSON
- Error payload/message
- Research suggestion payload
- Learning metadata

### Ingestion and Structure Intelligence

Primary file:
- `app/ingestion/structure_intelligence.py`

Responsibilities:
- Safe ZIP extraction (path traversal protection)
- Recursive CSV discovery
- Participant grouping (folder or filename patterns)
- Timestamp detection and normalization
- Schema inference (rule + optional LLM fallback)
- CSV validation and malformed data rejection

### Fusion Core

Primary files:
- `app/core/fusion_engine.py`
- `app/agent/loop.py`

Pipeline stages:
1. Timestamp parsing and validation
2. Optional agentic pre-processing
3. Sampling-rate estimation
4. Offset correction
5. Master-grid resampling
6. Multi-dataset merge
7. Transparency report generation
8. Visual overlays generation

### Agentic Runtime

Primary file:
- `app/agent/runtime.py`

Behavior:
- Propose safe transformations
- Evaluate candidate impact
- Accept only if improvement exceeds threshold
- Emit accepted/rejected action traces

Supported action classes:
- Scale accelerometer units
- Invert selected axis signs
- Median smoothing for noisy signals

### Scoring and Drift

Primary files:
- `app/core/hqscore_v4.py`
- `app/core/drift_analysis.py`

Outputs:
- Overall HQScore v4
- Component scores and advanced metric traces
- Drift classification and trend points

### Continual Learning

Primary file:
- `app/core/continual_learning.py`

Responsibilities:
- Build feature vectors from historical jobs
- Train lightweight regressors
- Predict candidate sampling rate and expected HQScore
- Return confidence and trend for adaptive panel

### Research Suggestion Engine

Primary files:
- `app/research/openalex_client.py`
- `app/research/research_suggestion_engine.py`

Responsibilities:
- Build search query from modalities/task
- Fetch and rank papers from OpenAlex
- Derive recommendation summary and rate guidance

## Frontend Layers

Root:
- `sensorfusion-dashboard/`

Entry pages:
- `app/page.tsx`: upload/hero
- `app/results/page.tsx`: result dashboard route

Key components:
- `Hero.tsx`: upload flow and `/fuse` submission
- `ResultsPage.tsx`: polling and result orchestration
- `FusionProgress.tsx`: async progress UI
- `FusionTransparencyPanel.tsx`
- `HQScorePanel.tsx`
- `HQScoreBreakdown.tsx`
- `DriftAnalysisPanel.tsx`
- `AlignmentDashboard.tsx`
- `DatasetStructureReport.tsx`
- `DatasetIntelligencePanel.tsx`
- `AgenticDecisionPanel.tsx`
- `AdaptiveLearningPanel.tsx`
- `ResearchSuggestionPanel.tsx`

## Error Model

All structured failures should follow:

```json
{
  "status": "failed",
  "error_type": "invalid_csv",
  "message": "Invalid or corrupted CSV file.",
  "details": {}
}
```

Completed with warnings:

```json
{
  "status": "completed_with_warnings",
  "warnings": ["Non-numeric columns ignored."],
  "fusion_report": {}
}
```

## Runtime Configuration Map

Main categories:
- Job timeout and ingestion limits
- Agentic runtime toggles
- Adaptive learning thresholds
- LLM schema inference model/timeouts
- Frontend API base URL variables

See root `README.md` for exact env keys.

## Design Principles

- Transparency-first: every major decision is surfaced in report payloads
- Safe fallbacks: failures are structured, not silent
- Async-first UX: long operations use job polling and progress
- Local-first operation with optional cloud enrichment (OpenAI/OpenAlex)
