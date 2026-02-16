"use client";

import { useRouter } from "next/navigation";
import Hero from "./components/Hero";
import type { FuseJobCreateResponse, FuseResponse } from "./types/fusion";

const INLINE_RESULT_SESSION_KEY = "sensorfusion:inline_result";

export default function App() {
  const router = useRouter();

  const goToResults = (jobId: string) => {
    router.push(`/results?job_id=${encodeURIComponent(jobId)}`);
  };

  const handleJobCreated = (job: FuseJobCreateResponse) => {
    goToResults(job.job_id);
  };

  const handleInlineResult = (result: FuseResponse) => {
    try {
      sessionStorage.setItem(INLINE_RESULT_SESSION_KEY, JSON.stringify(result));
    } catch {
      // Best-effort only; user still gets redirected.
    }
    router.push("/results?inline=1");
  };

  return (
    <div className="size-full bg-black text-white">
      <Hero onUploadSuccess={handleInlineResult} onJobCreated={handleJobCreated} />
    </div>
  );
}
