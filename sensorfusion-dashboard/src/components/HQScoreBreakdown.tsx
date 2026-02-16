"use client";

import { motion } from "motion/react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { HQScoreV4 } from "../types/fusion";

interface HQScoreBreakdownProps {
  hqscoreV4: HQScoreV4;
}

const EXPLANATIONS: Record<string, string> = {
  distribution_similarity: "KL divergence + Wasserstein based alignment of overlapping distributions.",
  spectral_similarity: "FFT dominant frequency agreement and spectral coherence.",
  temporal_alignment_strength: "Cross-correlation peak strength across synchronized signals.",
  missingness_penalty: "Penalty from modality-weighted missing values (lower is better).",
  sensor_coverage: "Coverage of expected modality channels in fused output.",
  stability_factor: "Temporal stability under drift + SNR consistency.",
};

const LABELS: Record<string, string> = {
  distribution_similarity: "Distribution",
  spectral_similarity: "Spectral",
  temporal_alignment_strength: "Temporal",
  missingness_penalty: "Missingness",
  sensor_coverage: "Coverage",
  stability_factor: "Stability",
};

function scoreClass(score: number) {
  if (score >= 0.8) return "text-emerald-300";
  if (score >= 0.6) return "text-amber-300";
  return "text-rose-300";
}

export default function HQScoreBreakdown({ hqscoreV4 }: HQScoreBreakdownProps) {
  const components = hqscoreV4.components;

  const radarData = [
    {
      key: "distribution_similarity",
      metric: LABELS.distribution_similarity,
      value: components.distribution_similarity,
    },
    {
      key: "spectral_similarity",
      metric: LABELS.spectral_similarity,
      value: components.spectral_similarity,
    },
    {
      key: "temporal_alignment_strength",
      metric: LABELS.temporal_alignment_strength,
      value: components.temporal_alignment_strength,
    },
    {
      key: "missingness_penalty",
      metric: LABELS.missingness_penalty,
      value: 1 - components.missingness_penalty,
    },
    {
      key: "sensor_coverage",
      metric: LABELS.sensor_coverage,
      value: components.sensor_coverage,
    },
    {
      key: "stability_factor",
      metric: LABELS.stability_factor,
      value: components.stability_factor,
    },
  ];

  const componentRows = [
    ["distribution_similarity", components.distribution_similarity],
    ["spectral_similarity", components.spectral_similarity],
    ["temporal_alignment_strength", components.temporal_alignment_strength],
    ["missingness_penalty", components.missingness_penalty],
    ["sensor_coverage", components.sensor_coverage],
    ["stability_factor", components.stability_factor],
  ] as const;

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xl font-semibold text-white">HQScore v4 Breakdown</h3>
        <span className="rounded-full border border-cyan-400/40 bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-200">
          Overall: {hqscoreV4.overall.toFixed(3)}
        </span>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-white/10 bg-black/20 p-3">
          <div className="w-full min-w-0">
            <ResponsiveContainer width="100%" height={300} minWidth={0} minHeight={300}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.15)" />
                <PolarAngleAxis dataKey="metric" tick={{ fill: "#d1d5db", fontSize: 12 }} />
                <PolarRadiusAxis domain={[0, 1]} tick={{ fill: "#9ca3af", fontSize: 10 }} />
                <Tooltip
                  formatter={(value, _name, payload) => {
                    const numericValue =
                      typeof value === "number" ? value : Number(value ?? 0);
                    const row = payload?.payload as { key?: string } | undefined;
                    const key = row?.key ?? "";
                    const suffix = key === "missingness_penalty" ? " (inverted for chart)" : "";
                    return [`${numericValue.toFixed(3)}${suffix}`, EXPLANATIONS[key] || key];
                  }}
                  contentStyle={{
                    background: "rgba(3, 7, 18, 0.95)",
                    border: "1px solid rgba(255,255,255,0.16)",
                    borderRadius: "10px",
                  }}
                />
                <Radar
                  dataKey="value"
                  stroke="#22d3ee"
                  fill="#22d3ee"
                  fillOpacity={0.2}
                  strokeWidth={2}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="space-y-2">
          {componentRows.map(([key, value]) => (
            <div key={key} className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-white">{LABELS[key]}</p>
                <p className={`text-sm font-semibold ${scoreClass(key === "missingness_penalty" ? 1 - value : value)}`}>
                  {value.toFixed(3)}
                </p>
              </div>
              <p className="mt-1 text-xs text-gray-400">{EXPLANATIONS[key]}</p>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
