"use client";

import { motion } from "motion/react";
import { BookOpen, Sparkles } from "lucide-react";
import { useState } from "react";
import type { ResearchSuggestion } from "../types/fusion";

interface ResearchSuggestionPanelProps {
  suggestion: ResearchSuggestion;
  onApplySuggestedSamplingRate?: (samplingRate: number) => Promise<void> | void;
  applying?: boolean;
}

export default function ResearchSuggestionPanel({
  suggestion,
  onApplySuggestedSamplingRate,
  applying = false,
}: ResearchSuggestionPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const papers = Array.isArray(suggestion.papers) ? suggestion.papers : [];
  const recommendedSamplingRate = suggestion.recommended_sampling_rate;
  const canApply = typeof recommendedSamplingRate === "number";
  const visiblePapers = expanded ? papers : papers.slice(0, 3);

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="mt-6 rounded-2xl border border-violet-400/20 bg-gradient-to-br from-violet-500/10 via-blue-500/5 to-transparent p-6 backdrop-blur-xl"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xl font-semibold text-white">Research Suggestions</h3>
        <span className="inline-flex items-center gap-2 rounded-full border border-violet-300/30 bg-violet-500/15 px-3 py-1 text-xs font-semibold text-violet-200">
          <Sparkles className="size-3.5" />
          Research Powered
        </span>
      </div>

      <p className="mt-2 text-sm text-gray-300">{suggestion.summary}</p>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
          <p className="text-xs text-gray-400">Recommended Sampling Rate</p>
          <p className="mt-1 text-lg font-semibold text-cyan-300">
            {canApply ? `${recommendedSamplingRate} Hz` : "Not available"}
          </p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
          <p className="text-xs text-gray-400">Confidence</p>
          <p className="mt-1 text-lg font-semibold text-violet-300">
            {(suggestion.confidence * 100).toFixed(0)}%
          </p>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-white/10 bg-black/20 p-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-semibold text-white">Top Cited Papers</p>
          {papers.length > 3 && (
            <button
              type="button"
              onClick={() => setExpanded((prev) => !prev)}
              className="text-xs text-cyan-300 hover:text-cyan-200"
            >
              {expanded ? "Show less" : `Show all (${papers.length})`}
            </button>
          )}
        </div>

        <div className="mt-2 space-y-2">
          {visiblePapers.map((paper, idx) => (
            <div key={`${paper.title}-${idx}`} className="rounded-md border border-white/10 bg-white/5 p-3">
              <a
                href={paper.url || undefined}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-start gap-2 text-sm font-medium text-blue-200 hover:text-blue-100"
              >
                <BookOpen className="mt-0.5 size-4 shrink-0" />
                <span>{paper.title}</span>
              </a>
              <div className="mt-1 flex items-center gap-2 text-xs text-gray-400">
                <span>{paper.year ?? "n/a"}</span>
                <span className="rounded-full border border-white/15 bg-white/10 px-2 py-0.5 text-amber-300">
                  {paper.citation_count} citations
                </span>
              </div>
            </div>
          ))}
          {papers.length === 0 && (
            <div className="rounded-md border border-white/10 bg-white/5 p-3 text-sm text-gray-400">
              No research papers found
            </div>
          )}
        </div>
      </div>

      <button
        type="button"
        disabled={applying || !canApply}
        onClick={() =>
          canApply ? onApplySuggestedSamplingRate?.(recommendedSamplingRate) : undefined
        }
        className="mt-4 inline-flex items-center justify-center rounded-lg border border-cyan-400/40 bg-cyan-500/15 px-4 py-2 text-sm font-semibold text-cyan-200 hover:bg-cyan-500/25 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {applying ? "Applying suggestion..." : "Apply Suggested Sampling Rate"}
      </button>
    </motion.div>
  );
}
