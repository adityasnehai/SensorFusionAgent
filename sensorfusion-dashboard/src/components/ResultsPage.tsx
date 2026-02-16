"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import AlignmentDashboard from "./AlignmentDashboard";
import AdaptiveLearningPanel from "./AdaptiveLearningPanel";
import AgenticDecisionPanel from "./AgenticDecisionPanel";
import DatasetStructureReport from "./DatasetStructureReport";
import DatasetIntelligencePanel from "./DatasetIntelligencePanel";
import DriftAnalysisPanel from "./DriftAnalysisPanel";
import FusionProgress from "./FusionProgress";
import FusionTransparencyPanel from "./FusionTransparencyPanel";
import HQScorePanel from "./HQScorePanel";
import HQScoreBreakdown from "./HQScoreBreakdown";
import ResearchSuggestionPanel from "./ResearchSuggestionPanel";
import type {
  FuseJobCreateResponse,
  FuseResponse,
  JobStatusResponse,
  ResearchSuggestion,
  ResearchSuggestionStatusResponse,
} from "../types/fusion";

const BACKEND_BASE_URL =
  process.env.NEXT_PUBLIC_FUSE_API_BASE ?? "http://localhost:8000";
const INLINE_RESULT_SESSION_KEY = "sensorfusion:inline_result";

type UiJobStatus = "idle" | "processing" | "completed" | "failed";

export default function ResultsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryJobId = searchParams.get("job_id");
  const inlineMode = searchParams.get("inline");
  const [result, setResult] = useState<FuseResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobStatus, setJobStatus] = useState<UiJobStatus>("idle");
  const [researchSuggestion, setResearchSuggestion] = useState<ResearchSuggestion | null>(null);
  const [applyingSuggestion, setApplyingSuggestion] = useState(false);

  const downloadUrl = useMemo(() => {
    if (!result?.download) return null;
    if (result.download.startsWith("http://") || result.download.startsWith("https://")) {
      return result.download;
    }
    return `${BACKEND_BASE_URL}${result.download}`;
  }, [result]);

  useEffect(() => {
    if (queryJobId) {
      setJobId(queryJobId);
      setJobProgress(0);
      setJobStatus("processing");
      setResult(null);
      setResearchSuggestion(null);
      setUploadError(null);
      return;
    }

    if (inlineMode === "1") {
      try {
        const raw = sessionStorage.getItem(INLINE_RESULT_SESSION_KEY);
        if (raw) {
          const inlineResult = JSON.parse(raw) as FuseResponse;
          setResult(inlineResult);
          setResearchSuggestion(inlineResult.research_suggestion ?? null);
          setJobStatus("completed");
          setJobProgress(100);
        } else {
          setUploadError("No result found. Start a new analysis.");
          setJobStatus("failed");
        }
      } catch {
        setUploadError("Unable to load analysis result. Start a new analysis.");
        setJobStatus("failed");
      } finally {
        sessionStorage.removeItem(INLINE_RESULT_SESSION_KEY);
      }
      return;
    }

    setJobId(null);
    setJobStatus("idle");
  }, [queryJobId, inlineMode]);

  useEffect(() => {
    if (!jobId || jobStatus !== "processing") return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const pollStatus = async () => {
      try {
        const response = await fetch(`${BACKEND_BASE_URL}/status/${jobId}`);
        const data = (await response.json()) as JobStatusResponse;

        if (!response.ok) {
          const errorMessage =
            (data as { message?: string; detail?: string }).message ||
            (data as { message?: string; detail?: string }).detail ||
            "Failed to fetch job status.";
          throw new Error(errorMessage);
        }

        if (typeof data.progress === "number") {
          setJobProgress(Math.max(0, Math.min(100, data.progress)));
        }

        const researchResponse = await fetch(`${BACKEND_BASE_URL}/research_suggestions/${jobId}`);
        if (researchResponse.ok) {
          const researchData = (await researchResponse.json()) as ResearchSuggestionStatusResponse;
          if (researchData.research_suggestion) {
            setResearchSuggestion(researchData.research_suggestion);
          }
        }

        if (data.status === "completed" || data.status === "completed_with_warnings") {
          setJobStatus("completed");
          setJobProgress(100);
          if (data.result) {
            setResult(data.result);
            if (data.result.research_suggestion) {
              setResearchSuggestion(data.result.research_suggestion);
            }
            setUploadError(null);
          }
          return;
        }

        if (data.status === "failed") {
          setJobStatus("failed");
          const errorMessage =
            data.error?.message || data.error_message || "Fusion job failed.";
          setUploadError(errorMessage);
          return;
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Job polling failed.";
        setJobStatus("failed");
        setUploadError(message);
        return;
      }

      if (!cancelled) {
        timer = setTimeout(pollStatus, 2000);
      }
    };

    void pollStatus();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, jobStatus]);

  const handleApplySuggestedSamplingRate = async (samplingRate: number) => {
    if (!jobId) return;

    setApplyingSuggestion(true);
    setUploadError(null);

    try {
      const response = await fetch(
        `${BACKEND_BASE_URL}/research_suggestions/${jobId}/apply?sampling_rate=${encodeURIComponent(
          samplingRate
        )}`,
        { method: "POST" }
      );

      const data = (await response.json()) as FuseJobCreateResponse & {
        detail?: string;
        message?: string;
      };
      if (!response.ok || typeof data.job_id !== "string") {
        throw new Error(data.message || data.detail || "Failed to apply research suggestion.");
      }

      setJobId(data.job_id);
      setJobStatus("processing");
      setJobProgress(0);
      setResult(null);
      setResearchSuggestion(null);
      router.replace(`/results?job_id=${encodeURIComponent(data.job_id)}`);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to apply research suggestion.";
      setUploadError(message);
    } finally {
      setApplyingSuggestion(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white">
      <section className="mx-auto w-full max-w-5xl px-6 pb-16 pt-8">
        <button
          type="button"
          onClick={() => router.push("/")}
          className="mb-6 inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/5 px-3 py-2 text-sm text-gray-200 hover:bg-white/10"
        >
          <ArrowLeft className="size-4" />
          Back to Upload
        </button>

        <h1 className="mb-2 text-2xl font-semibold text-white">Analysis Dashboard</h1>
        <p className="mb-6 text-sm text-gray-400">
          Fusion results, transparency metrics, and alignment validation.
        </p>

        {jobStatus === "processing" && <FusionProgress progress={jobProgress} />}

        {result && (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
            {result.structure_report && <DatasetStructureReport report={result.structure_report} />}
            {result.fusion_report?.schema_inference && result.fusion_report?.task_inference && (
              <DatasetIntelligencePanel
                schemaInference={result.fusion_report.schema_inference}
                taskInference={result.fusion_report.task_inference}
              />
            )}
            {result.fusion_report?.agentic_layer && (
              <div className="mt-6">
                <AgenticDecisionPanel agenticLayer={result.fusion_report.agentic_layer} />
              </div>
            )}
            {result.fusion_report?.adaptive_layer && (
              <div className="mt-6">
                <AdaptiveLearningPanel adaptiveLayer={result.fusion_report.adaptive_layer} />
              </div>
            )}
            <div className="mt-6">
              <HQScorePanel score={result.hqscore ?? 0} />
            </div>
            {result.fusion_report?.hqscore_v4 && (
              <HQScoreBreakdown hqscoreV4={result.fusion_report.hqscore_v4} />
            )}
            {result.fusion_report?.drift_analysis && (
              <DriftAnalysisPanel driftAnalysis={result.fusion_report.drift_analysis} />
            )}
            {result.fusion_report && (
              <FusionTransparencyPanel
                report={result.fusion_report}
                confidence={result.confidence}
              />
            )}
            {researchSuggestion && (
              <ResearchSuggestionPanel
                suggestion={researchSuggestion}
                onApplySuggestedSamplingRate={handleApplySuggestedSamplingRate}
                applying={applyingSuggestion}
              />
            )}
            <AlignmentDashboard visualData={result.visual_data} loading={false} />
            {typeof result.sampling_rate === "number" && (
              <p className="mt-4 text-sm text-gray-300">
                Sampling rate: <span className="font-semibold text-white">{result.sampling_rate} Hz</span>
              </p>
            )}
            {downloadUrl && (
              <a
                href={downloadUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-4 inline-block rounded-lg border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-300 hover:bg-cyan-400/20"
              >
                Download fused output
              </a>
            )}
          </div>
        )}

        {uploadError && (
          <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {uploadError}
          </div>
        )}

        {!result && jobStatus === "idle" && !uploadError && (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-gray-300">
            No analysis selected. Start from upload page.
          </div>
        )}
      </section>
    </div>
  );
}
