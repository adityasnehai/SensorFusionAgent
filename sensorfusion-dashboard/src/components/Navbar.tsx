import { Brain } from "lucide-react";

export default function Navbar() {
  return (
    <header className="sticky top-0 z-20 border-b border-white/10 bg-black/60 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 p-2">
            <Brain className="size-5 text-cyan-300" />
          </div>
          <div>
            <p className="bg-gradient-to-r from-blue-300 to-violet-300 bg-clip-text text-lg font-semibold text-transparent">
              SensorFusionAgent
            </p>
            <p className="text-xs text-slate-400">Research-Aware Fusion Engine</p>
          </div>
        </div>

        <nav className="hidden items-center gap-6 text-sm text-slate-300 md:flex">
          <a className="transition hover:text-white" href="#upload">
            Upload
          </a>
          <a className="transition hover:text-white" href="#features">
            Features
          </a>
          <a className="transition hover:text-white" href="#score">
            HQScore
          </a>
        </nav>

        <div className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-slate-300">
          v1.1
        </div>
      </div>
    </header>
  );
}
