"use client";

interface HQScorePanelProps {
  score: number;
}

export default function HQScorePanel({ score }: HQScorePanelProps) {
  const safeScore = Number.isFinite(score) ? Math.max(0, Math.min(1, score)) : 0;
  const percent = safeScore * 100;
  const radius = 68;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (percent / 100) * circumference;

  return (
    <div>
      <h2 className="text-xl font-semibold text-white">Harmonization Quality Score</h2>
      <p className="mt-1 text-sm text-gray-400">
        Model confidence for the fused IMU harmonization output.
      </p>

      <div className="mt-6 flex items-center justify-center">
        <div className="relative h-44 w-44">
          <svg className="h-44 w-44 -rotate-90" viewBox="0 0 160 160" aria-hidden="true">
            <circle cx="80" cy="80" r={radius} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="12" />
            <circle
              cx="80"
              cy="80"
              r={radius}
              fill="none"
              stroke="url(#hqscoreGradient)"
              strokeLinecap="round"
              strokeWidth="12"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
            />
            <defs>
              <linearGradient id="hqscoreGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#60a5fa" />
                <stop offset="50%" stopColor="#22d3ee" />
                <stop offset="100%" stopColor="#a78bfa" />
              </linearGradient>
            </defs>
          </svg>

          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold text-white">{percent.toFixed(1)}%</span>
            <span className="text-xs uppercase tracking-wider text-gray-400">HQScore</span>
          </div>
        </div>
      </div>
    </div>
  );
}
