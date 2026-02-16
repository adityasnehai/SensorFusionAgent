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
import type { VisualDataPoint, VisualData } from "../types/fusion";

interface AlignmentDashboardProps {
  visualData?: VisualData;
  loading?: boolean;
}

const LINE_PALETTES = [
  ["#60a5fa", "#22d3ee"],
  ["#a78bfa", "#f472b6"],
  ["#34d399", "#22c55e"],
  ["#f59e0b", "#f97316"],
];

function MagnitudeChart({
  title,
  data,
  chartId,
}: {
  title: string;
  data: VisualDataPoint[];
  chartId: string;
}) {
  const datasetKeys = data.length
    ? Object.keys(data[0]).filter((key) => key.startsWith("dataset_"))
    : [];

  return (
    <div className="rounded-xl border border-white/10 bg-black/30 p-4">
      <h4 className="text-sm font-semibold text-white">{title}</h4>
      <p className="mt-1 text-xs text-gray-400">
        Overlay of synchronized magnitude signals after alignment.
      </p>

      <div className="mt-4 w-full min-w-0">
        <ResponsiveContainer width="100%" height={288} minWidth={0} minHeight={288}>
          <LineChart data={data}>
            <defs>
              {datasetKeys.map((key, idx) => {
                const palette = LINE_PALETTES[idx % LINE_PALETTES.length];
                const gradientId = `${chartId}-${key}-gradient`;
                return (
                  <linearGradient id={gradientId} key={gradientId} x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor={palette[0]} />
                    <stop offset="100%" stopColor={palette[1]} />
                  </linearGradient>
                );
              })}
            </defs>

            <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="4 4" />
            <XAxis dataKey="timestamp" tick={{ fill: "#9ca3af", fontSize: 11 }} minTickGap={28} />
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

            {datasetKeys.map((key) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={`url(#${chartId}-${key}-gradient)`}
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={false}
                name={key.replace("_", " ")}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function AlignmentDashboard({ visualData, loading }: AlignmentDashboardProps) {
  if (loading) {
    return (
      <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
        <h3 className="text-xl font-semibold text-white">Alignment Dashboard</h3>
        <p className="mt-2 text-sm text-gray-300">Loading synchronized alignment visualizations...</p>
      </div>
    );
  }

  if (!visualData) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl"
    >
      <h3 className="text-xl font-semibold text-white">Visual Alignment &amp; Validation</h3>
      <p className="mt-2 text-sm text-gray-300">
        Time-series overlays provide visual evidence that synchronization and harmonization worked.
      </p>

      <div className="mt-5 space-y-4">
        <MagnitudeChart
          title="Accelerometer Magnitude Overlay"
          data={visualData.acc_magnitude_overlay}
          chartId="acc-chart"
        />
        <MagnitudeChart
          title="Gyroscope Magnitude Overlay"
          data={visualData.gyro_magnitude_overlay}
          chartId="gyro-chart"
        />
      </div>
    </motion.div>
  );
}
