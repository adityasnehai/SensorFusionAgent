"use client";

import { motion } from "framer-motion";
import type { AgenticLayerInfo } from "../types/fusion";

type Props = {
  agenticLayer: AgenticLayerInfo;
};

export default function AgenticDecisionPanel({ agenticLayer }: Props) {
  const badgeClass = agenticLayer.used
    ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-200"
    : "border-amber-400/40 bg-amber-500/15 text-amber-200";

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-2xl border border-cyan-400/20 bg-cyan-500/5 p-5"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-cyan-100">Agentic Decision Layer</h2>
          <p className="text-xs text-cyan-100/70">
            Planner/Executor/Observer loop with guarded action application.
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-medium ${badgeClass}`}>
          {agenticLayer.used ? "Actions Applied" : "No Action Applied"}
        </span>
      </div>

      <div className="grid gap-3 text-sm text-gray-200 md:grid-cols-3">
        <div className="rounded-lg border border-white/10 bg-white/5 p-3">
          <p className="text-xs text-gray-400">Policy</p>
          <p className="font-medium text-white">{agenticLayer.policy}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/5 p-3">
          <p className="text-xs text-gray-400">Confidence</p>
          <p className="font-medium text-white">{Math.round(agenticLayer.confidence * 100)}%</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/5 p-3">
          <p className="text-xs text-gray-400">Net Improvement</p>
          <p className="font-medium text-white">{agenticLayer.net_improvement.toFixed(4)}</p>
        </div>
      </div>

      <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-3 text-xs text-gray-300">
        <p>Iterations: {agenticLayer.iterations}</p>
        <p>Initial score: {agenticLayer.initial_quality_score.toFixed(4)}</p>
        <p>Final score: {agenticLayer.final_quality_score.toFixed(4)}</p>
        <p>Stop reason: {agenticLayer.stop_reason}</p>
      </div>

      {agenticLayer.accepted_actions.length > 0 && (
        <div className="mt-3 space-y-2">
          {agenticLayer.accepted_actions.slice(0, 5).map((action) => (
            <div
              key={`${action.action_id}-${action.iteration}`}
              className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs text-gray-300"
            >
              <p className="font-medium text-white">
                {action.dataset_id} · {action.action_type}
              </p>
              <p>{action.rationale}</p>
              <p>
                score {action.score_before.toFixed(4)} → {action.score_after.toFixed(4)} (
                {action.improvement >= 0 ? "+" : ""}
                {action.improvement.toFixed(4)})
              </p>
            </div>
          ))}
        </div>
      )}
    </motion.section>
  );
}
