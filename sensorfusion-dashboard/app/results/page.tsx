import { Suspense } from "react";
import ResultsPage from "../../src/components/ResultsPage";

export default function Results() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-black px-6 py-10 text-sm text-gray-300">
          Loading results...
        </div>
      }
    >
      <ResultsPage />
    </Suspense>
  );
}
