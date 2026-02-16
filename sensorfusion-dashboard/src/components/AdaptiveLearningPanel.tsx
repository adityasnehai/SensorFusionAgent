"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import type { AdaptiveLayerInfo } from "../types/fusion";

interface AdaptiveLearningPanelProps {
  adaptiveLayer: AdaptiveLayerInfo;
}

function confidenceClass(score: number) {
  if (score >= 0.8) return "text-emerald-300";
  if (score >= 0.6) return "text-amber-300";
  return "text-rose-300";
}

export default function AdaptiveLearningPanel({ adaptiveLayer }: AdaptiveLearningPanelProps) {
  const trend = Array.isArray(adaptiveLayer.performance_trend)
    ? adaptiveLayer.performance_trend.slice(-30)
    : [];
  const chartHostRef = useRef<HTMLDivElement | null>(null);
  const [chartWidth, setChartWidth] = useState(0);

  useEffect(() => {
    const host = chartHostRef.current;
    if (!host) return;

    const updateReady = () => {
      const rect = host.getBoundingClientRect();
      setChartWidth(rect.width > 0 ? Math.floor(rect.width) : 0);
    };

    updateReady();
    const observer = new ResizeObserver(updateReady);
    observer.observe(host);
    return () => observer.disconnect();
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="rounded-2xl border border-emerald-400/20 bg-gradient-to-br from-emerald-500/10 via-slate-900/70 to-black/70 p-6 backdrop-blur-xl"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xl font-semibold text-white">Adaptive Learning</h3>
        <span className="rounded-full border border-emerald-300/30 bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-200">
          System Learning Over Time
        </span>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-white/10 bg-black/25 p-3">
          <p className="text-xs text-gray-400">Adaptive Decision Used</p>
          <p className="mt-1 text-sm font-semibold text-white">{adaptiveLayer.used ? "Yes" : "No"}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/25 p-3">
          <p className="text-xs text-gray-400">Model Confidence</p>
          <p className={`mt-1 text-sm font-semibold ${confidenceClass(adaptiveLayer.confidence)}`}>
            {(adaptiveLayer.confidence * 100).toFixed(0)}%
          </p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/25 p-3">
          <p className="text-xs text-gray-400">Model Version</p>
          <p className="mt-1 text-sm font-semibold text-white">{adaptiveLayer.model_version}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/25 p-3">
          <p className="text-xs text-gray-400">Expected HQScore</p>
          <p className="mt-1 text-sm font-semibold text-cyan-300">
            {typeof adaptiveLayer.expected_hqscore === "number"
              ? adaptiveLayer.expected_hqscore.toFixed(3)
              : "n/a"}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-white/10 bg-black/25 p-3 text-sm text-gray-300">
          <p className="text-xs text-gray-400">Predicted Sampling Rate</p>
          <p className="mt-1 font-semibold text-white">
            {typeof adaptiveLayer.predicted_sampling_rate_hz === "number"
              ? `${adaptiveLayer.predicted_sampling_rate_hz.toFixed(2)} Hz`
              : "n/a"}
          </p>
          <p className="mt-2 text-xs text-gray-400">Applied Sampling Rate</p>
          <p className="mt-1 font-semibold text-white">
            {typeof adaptiveLayer.applied_sampling_rate_hz === "number"
              ? `${adaptiveLayer.applied_sampling_rate_hz.toFixed(2)} Hz`
              : "n/a"}
          </p>
        </div>

        <div className="rounded-lg border border-white/10 bg-black/25 p-3">
          <p className="text-sm font-semibold text-white">Performance Improvement Trend</p>
          <p className="mt-1 text-xs text-gray-400">Historical HQScore trajectory across completed jobs.</p>
          <div ref={chartHostRef} className="mt-3 h-44 w-full min-w-0">
            {chartWidth > 0 ? (
              <LineChart width={chartWidth} height={176} data={trend} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
                <XAxis dataKey="job_index" tick={{ fill: "#9ca3af", fontSize: 10 }} />
                <YAxis domain={[0, 1]} tick={{ fill: "#9ca3af", fontSize: 10 }} />
                <Tooltip
                  formatter={(value, name) => {
                    const numeric = typeof value === "number" ? value : Number(value ?? 0);
                    return [numeric.toFixed(3), String(name)];
                  }}
                  contentStyle={{
                    background: "rgba(3, 7, 18, 0.95)",
                    border: "1px solid rgba(255,255,255,0.16)",
                    borderRadius: "10px",
                  }}
                />
                <Line type="monotone" dataKey="hqscore" stroke="#22d3ee" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="moving_avg" stroke="#34d399" strokeWidth={2} dot={false} />
              </LineChart>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-gray-500">
                Preparing chart...
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
