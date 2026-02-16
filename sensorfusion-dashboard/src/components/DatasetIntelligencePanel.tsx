"use client";

import { motion } from "motion/react";
import { BrainCircuit, Sparkles } from "lucide-react";
import type { SchemaInferenceInfo, TaskInferenceInfo } from "../types/fusion";

interface DatasetIntelligencePanelProps {
  schemaInference: SchemaInferenceInfo;
  taskInference: TaskInferenceInfo;
}

function confidenceClass(score: number) {
  if (score >= 0.8) return "text-emerald-300";
  if (score >= 0.6) return "text-amber-300";
  return "text-rose-300";
}

export default function DatasetIntelligencePanel({
  schemaInference,
  taskInference,
}: DatasetIntelligencePanelProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mt-6 rounded-2xl border border-cyan-400/20 bg-gradient-to-br from-cyan-500/10 via-slate-900/70 to-black/70 p-6 backdrop-blur-xl"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xl font-semibold text-white">Dataset Intelligence</h3>
        <span className="inline-flex items-center gap-2 rounded-full border border-cyan-300/30 bg-cyan-500/15 px-3 py-1 text-xs font-semibold text-cyan-100">
          <Sparkles className="size-3.5" />
          AI-Assisted Inference
        </span>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-white/10 bg-black/25 p-3">
          <p className="text-xs text-gray-400">Schema Inference Method</p>
          <p className="mt-1 text-sm font-semibold uppercase tracking-wide text-white">
            {schemaInference.method.replace(/_/g, " ")}
          </p>
          <p className={`mt-1 text-sm font-semibold ${confidenceClass(schemaInference.confidence)}`}>
            {(schemaInference.confidence * 100).toFixed(0)}% confidence
          </p>
        </div>

        <div className="rounded-lg border border-white/10 bg-black/25 p-3">
          <p className="text-xs text-gray-400">Predicted Task</p>
          <p className="mt-1 inline-flex items-center gap-2 text-sm font-semibold text-white">
            <BrainCircuit className="size-4 text-cyan-300" />
            {taskInference.predicted_task}
          </p>
          <p className={`mt-1 text-sm font-semibold ${confidenceClass(taskInference.confidence)}`}>
            {(taskInference.confidence * 100).toFixed(0)}% confidence
          </p>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-white/10 bg-black/25 p-3 text-sm text-gray-300">
        <p className="font-medium text-white">Reasoning</p>
        <p className="mt-1">{taskInference.reasoning}</p>
        {schemaInference.reasoning_summary && (
          <p className="mt-2 text-xs text-cyan-200/90">Schema note: {schemaInference.reasoning_summary}</p>
        )}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border border-white/10 bg-black/25 p-3">
          <p className="text-xs text-gray-400">Suggested Window</p>
          <p className="mt-1 text-sm font-semibold text-white">
            {typeof taskInference.suggested_window_seconds === "number"
              ? `${taskInference.suggested_window_seconds}s`
              : "Not available"}
          </p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/25 p-3">
          <p className="text-xs text-gray-400">Suggested Sampling Rate</p>
          <p className="mt-1 text-sm font-semibold text-white">
            {typeof taskInference.suggested_sampling_rate_hz === "number"
              ? `${taskInference.suggested_sampling_rate_hz} Hz`
              : "Not available"}
          </p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/25 p-3">
          <p className="text-xs text-gray-400">HQScore Weight Profile</p>
          <p className="mt-1 text-sm font-semibold text-white">
            {taskInference.hqscore_weight_profile
              ? taskInference.hqscore_weight_profile.replace(/_/g, " ")
              : "balanced"}
          </p>
        </div>
      </div>
    </motion.div>
  );
}
