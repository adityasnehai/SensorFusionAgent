"use client";

import { motion } from "motion/react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DriftAnalysis } from "../types/fusion";

interface DriftAnalysisPanelProps {
  driftAnalysis: DriftAnalysis;
}

function badgeClass(type: string) {
  if (type === "none") return "border-emerald-400/40 bg-emerald-400/10 text-emerald-300";
  if (type === "minor") return "border-amber-400/40 bg-amber-400/10 text-amber-300";
  return "border-rose-400/40 bg-rose-400/10 text-rose-300";
}

export default function DriftAnalysisPanel({ driftAnalysis }: DriftAnalysisPanelProps) {
  const trend = driftAnalysis.offset_trend || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xl font-semibold text-white">Drift Analysis</h3>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold capitalize ${badgeClass(driftAnalysis.drift_type)}`}>
          {driftAnalysis.drift_type}
        </span>
      </div>

      <p className="mt-2 text-sm text-gray-300">
        {driftAnalysis.explanation || "Sliding-window alignment stability after synchronization."}
      </p>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
          <p className="text-xs text-gray-400">Average Window Offset</p>
          <p className="mt-1 text-lg font-semibold text-white">{driftAnalysis.average_window_offset.toFixed(4)} s</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
          <p className="text-xs text-gray-400">DTW Score</p>
          <p className="mt-1 text-lg font-semibold text-cyan-300">{driftAnalysis.dtw_score.toFixed(4)}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
          <p className="text-xs text-gray-400">Stability Score</p>
          <p className="mt-1 text-lg font-semibold text-violet-300">{driftAnalysis.stability_score.toFixed(4)}</p>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-white/10 bg-black/20 p-3">
        <p className="text-sm font-semibold text-white">Offset Trend Over Time</p>
        {trend.length > 0 ? (
          <div className="mt-3 w-full min-w-0">
            <ResponsiveContainer width="100%" height={280} minWidth={0} minHeight={280}>
              <LineChart data={trend}>
                <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="4 4" />
                <XAxis
                  dataKey="timestamp"
                  tick={{ fill: "#9ca3af", fontSize: 11 }}
                  minTickGap={28}
                />
                <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    background: "rgba(3, 7, 18, 0.95)",
                    border: "1px solid rgba(255,255,255,0.16)",
                    borderRadius: "10px",
                  }}
                  labelStyle={{ color: "#d1d5db" }}
                />
                <Legend wrapperStyle={{ color: "#d1d5db", fontSize: 12 }} />
                <Line
                  type="monotone"
                  dataKey="offset_seconds"
                  name="Offset (s)"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="correlation_strength"
                  name="Correlation"
                  stroke="#22d3ee"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="mt-2 text-sm text-gray-400">Not enough windows for trend visualization.</p>
        )}
      </div>
    </motion.div>
  );
}
