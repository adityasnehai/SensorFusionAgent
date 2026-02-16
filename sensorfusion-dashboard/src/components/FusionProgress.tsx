"use client";

import { Loader2 } from "lucide-react";
import { motion } from "motion/react";

interface FusionProgressProps {
  progress: number;
  statusText?: string;
}

export default function FusionProgress({ progress, statusText }: FusionProgressProps) {
  const normalized = Math.max(0, Math.min(100, progress));

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur-xl"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Loader2 className="size-4 animate-spin text-cyan-300" />
          <p className="text-sm text-gray-200">
            {statusText ?? "Fusion is running in background..."}
          </p>
        </div>
        <p className="text-sm font-semibold text-cyan-300">{normalized}%</p>
      </div>

      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-white/10">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-blue-500 via-cyan-400 to-purple-500"
          initial={{ width: 0 }}
          animate={{ width: `${normalized}%` }}
          transition={{ duration: 0.35 }}
        />
      </div>
    </motion.div>
  );
}
