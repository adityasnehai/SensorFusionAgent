"use client";

import { motion } from "motion/react";
import type { ConfidenceInfo, FusionReport } from "../types/fusion";

interface FusionTransparencyPanelProps {
  report: FusionReport;
  confidence?: ConfidenceInfo;
}

function confidenceBadgeClass(level: string) {
  if (level === "High") {
    return "border-emerald-400/40 bg-emerald-400/10 text-emerald-300";
  }
  if (level === "Medium") {
    return "border-amber-400/40 bg-amber-400/10 text-amber-300";
  }
  return "border-rose-400/40 bg-rose-400/10 text-rose-300";
}

export default function FusionTransparencyPanel({
  report,
  confidence,
}: FusionTransparencyPanelProps) {
  const resolvedConfidence = confidence ?? report.confidence;
  const overlap = report.dataset_metadata.overlap_window;
  const integrity = report.data_integrity;
  const alignment = report.alignment_decisions;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xl font-semibold text-white">Fusion Transparency</h3>
        <span
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${confidenceBadgeClass(
            resolvedConfidence.level
          )}`}
        >
          Confidence: {resolvedConfidence.level}
        </span>
      </div>

      <p className="mt-2 text-sm text-gray-300">{resolvedConfidence.reason}</p>
      {report.summary && <p className="mt-1 text-sm text-cyan-300">{report.summary}</p>}

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-black/20 p-4">
          <h4 className="text-sm font-semibold text-white">Dataset Metadata</h4>
          <div className="mt-3 space-y-2 text-sm text-gray-300">
            {report.dataset_metadata.datasets.map((item) => (
              <div key={item.dataset_id} className="rounded-lg border border-white/10 bg-white/5 p-3">
                <p className="font-medium text-white">{item.dataset_id}</p>
                <p>Sampling rate: {item.sampling_rate_hz.toFixed(2)} Hz</p>
                <p>Duration: {item.duration_seconds.toFixed(2)} sec</p>
              </div>
            ))}
            <div className="rounded-lg border border-white/10 bg-white/5 p-3">
              <p className="font-medium text-white">Overlap window</p>
              <p>
                {overlap.start_timestamp && overlap.end_timestamp
                  ? `${overlap.start_timestamp} -> ${overlap.end_timestamp}`
                  : "No overlap"}
              </p>
              <p>Duration: {overlap.duration_seconds.toFixed(2)} sec</p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-white/10 bg-black/20 p-4">
          <h4 className="text-sm font-semibold text-white">Alignment Decisions</h4>
          <div className="mt-3 space-y-2 text-sm text-gray-300">
            <div className="rounded-lg border border-white/10 bg-white/5 p-3">
              <p>
                Master sampling rate:{" "}
                <span className="font-medium text-white">
                  {alignment.master_sampling_rate_hz.toFixed(2)} Hz
                </span>
              </p>
              <p>Drift detected: {alignment.drift_detected ? "Yes" : "No"}</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/5 p-3">
              <p className="font-medium text-white">Offset corrections</p>
              <div className="mt-1 space-y-1">
                {alignment.offset_corrections.map((item) => (
                  <p key={item.dataset_id}>
                    {item.dataset_id}: {item.offset_seconds >= 0 ? "+" : ""}
                    {item.offset_seconds.toFixed(4)}s
                  </p>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/5 p-3">
              <p className="font-medium text-white">Resampling strategy</p>
              <div className="mt-1 space-y-1">
                {Object.entries(alignment.resampling_strategy).map(([key, value]) => (
                  <p key={key}>
                    {key}: {value}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-4">
        <h4 className="text-sm font-semibold text-white">Data Integrity</h4>
        <div className="mt-3 grid gap-3 text-sm text-gray-300 md:grid-cols-2">
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="font-medium text-white">Missing modalities</p>
            <p>{integrity.missing_modalities.length ? integrity.missing_modalities.join(", ") : "None"}</p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="font-medium text-white">Distribution divergence</p>
            <p>{integrity.distribution_divergence_score.toFixed(4)}</p>
          </div>
        </div>
        <div className="mt-3 rounded-lg border border-white/10 bg-white/5 p-3 text-sm text-gray-300">
          <p className="mb-1 font-medium text-white">Missingness by modality (%)</p>
          <div className="grid gap-1 md:grid-cols-2">
            {Object.entries(integrity.missingness_percentage_by_modality).map(([key, value]) => (
              <p key={key}>
                {key}: {value.toFixed(2)}%
              </p>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
