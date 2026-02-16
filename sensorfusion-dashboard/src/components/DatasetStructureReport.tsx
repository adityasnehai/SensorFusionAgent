"use client";

import { motion } from "motion/react";
import type { DatasetStructureReport as DatasetStructureReportType } from "../types/fusion";

interface DatasetStructureReportProps {
  report: DatasetStructureReportType;
}

export default function DatasetStructureReport({ report }: DatasetStructureReportProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl"
    >
      <h3 className="text-xl font-semibold text-white">Dataset Structure Intelligence</h3>
      <p className="mt-2 text-sm text-gray-300">
        Automatic structure and schema inference performed before harmonization.
      </p>

      <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
          <p className="text-xs text-gray-400">Participants Detected</p>
          <p className="mt-1 text-lg font-semibold text-white">{report.participants_detected}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
          <p className="text-xs text-gray-400">Files Detected</p>
          <p className="mt-1 text-lg font-semibold text-white">{report.files_detected}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
          <p className="text-xs text-gray-400">Grouping Strategy</p>
          <p className="mt-1 text-lg font-semibold capitalize text-white">{report.grouping_strategy.replace(/_/g, " ")}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
          <p className="text-xs text-gray-400">Schema Confidence</p>
          <p className="mt-1 text-lg font-semibold text-cyan-300">
            {(report.schema_inference_confidence * 100).toFixed(0)}%
          </p>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-gray-300">
        <p className="font-medium text-white">Detected Modalities</p>
        <p className="mt-1">
          {report.detected_modalities.length ? report.detected_modalities.join(", ") : "No known modalities detected"}
        </p>
      </div>

      {report.timestamp_ambiguous && (
        <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
          Timestamp ambiguity detected in one or more files. Best candidate was selected automatically.
        </div>
      )}

      {report.warnings.length > 0 && (
        <div className="mt-3 rounded-lg border border-rose-500/25 bg-rose-500/10 p-3 text-sm text-rose-200">
          <p className="font-medium text-rose-100">Ingestion warnings</p>
          <div className="mt-1 space-y-1">
            {report.warnings.slice(0, 5).map((warning, idx) => (
              <p key={`${warning}-${idx}`}>{warning}</p>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
