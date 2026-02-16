"use client";

import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  FileText,
  Loader2,
  Plus,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";

const MAX_DATASETS = 4;
const MIN_REQUIRED = 2;
const FUSE_API_URL = "http://localhost:8000/fuse";

interface DatasetUploadPanelProps {
  onUploadSuccess?: (data: unknown) => void;
  onUploadError?: (error: string) => void;
  className?: string;
}

type DatasetSlot = File | null;

const panelVariants = {
  hidden: { opacity: 0, y: 22 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45 } },
};

const dropZoneVariants = {
  idle: { scale: 1, opacity: 1 },
  active: { scale: 1.01, opacity: 1 },
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function isAccepted(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".csv") || name.endsWith(".zip");
}

function fileKey(file: File): string {
  return `${file.name}-${file.size}-${file.lastModified}`;
}

export default function DatasetUploadPanel({
  onUploadSuccess,
  onUploadError,
  className = "",
}: DatasetUploadPanelProps) {
  const [datasets, setDatasets] = useState<DatasetSlot[]>([
    null,
    null,
    null,
    null,
  ]);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const dataset1InputRef = useRef<HTMLInputElement | null>(null);
  const dataset2InputRef = useRef<HTMLInputElement | null>(null);
  const addMoreInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (folderInputRef.current) {
      folderInputRef.current.setAttribute("webkitdirectory", "");
      folderInputRef.current.setAttribute("directory", "");
    }
  }, []);

  const selectedCount = useMemo(
    () => datasets.filter(Boolean).length,
    [datasets]
  );
  const canAnalyze = datasets.slice(0, MIN_REQUIRED).every(Boolean);
  const canAddMore = selectedCount < MAX_DATASETS;

  const clearStatus = () => {
    setError(null);
    setSuccessMsg(null);
  };

  // Fill dataset slots with incoming files (optionally preferring extra slots first).
  const addFilesToSlots = (files: File[], preferExtraSlots: boolean) => {
    if (files.length === 0) return;

    clearStatus();
    let overflow = false;

    setDatasets((prev) => {
      const next = [...prev];
      const existing = new Set(prev.filter(Boolean).map((f) => fileKey(f as File)));

      for (const file of files) {
        if (!isAccepted(file)) continue;
        if (existing.has(fileKey(file))) continue;

        let idx = -1;
        if (preferExtraSlots) {
          idx = next.findIndex((slot, i) => i >= 2 && slot === null);
        }
        if (idx === -1) {
          idx = next.findIndex((slot) => slot === null);
        }
        if (idx === -1) {
          overflow = true;
          break;
        }
        next[idx] = file;
        existing.add(fileKey(file));
      }

      return next;
    });

    if (overflow) {
      const msg = `Maximum ${MAX_DATASETS} datasets allowed.`;
      setError(msg);
      onUploadError?.(msg);
    }
  };

  const assignFixedSlot = (slotIndex: 0 | 1, file: File | null) => {
    clearStatus();
    if (file && !isAccepted(file)) {
      const msg = "Only CSV and ZIP files are supported for fixed dataset slots.";
      setError(msg);
      onUploadError?.(msg);
      return;
    }

    setDatasets((prev) => {
      const next = [...prev];
      next[slotIndex] = file;
      return next;
    });
  };

  // Drag-and-drop handlers with visual state transitions.
  const onDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const onDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    addFilesToSlots(Array.from(e.dataTransfer.files), false);
  };

  const removeDataset = (index: number) => {
    clearStatus();
    setDatasets((prev) => prev.map((slot, i) => (i === index ? null : slot)));
  };

  const handleUpload = async () => {
    if (!canAnalyze) {
      const msg = "Dataset 1 and Dataset 2 are required.";
      setError(msg);
      onUploadError?.(msg);
      return;
    }

    setLoading(true);
    clearStatus();

    try {
      const formData = new FormData();
      datasets.forEach((file, index) => {
        if (file) formData.append(`dataset${index + 1}`, file);
      });

      const response = await fetch(FUSE_API_URL, {
        method: "POST",
        body: formData,
      });

      const text = await response.text();
      let data: unknown = text;
      try {
        data = text ? JSON.parse(text) : {};
      } catch {
        data = text;
      }

      if (!response.ok) {
        throw new Error(
          `Upload failed (${response.status}): ${
            typeof data === "string" ? data : "Server error"
          }`
        );
      }

      setSuccessMsg("Upload completed successfully.");
      onUploadSuccess?.(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed.";
      setError(msg);
      onUploadError?.(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.section
      variants={panelVariants}
      initial="hidden"
      animate="show"
      className={`mx-auto w-full max-w-4xl rounded-3xl border border-white/10 bg-slate-950/70 p-6 shadow-2xl backdrop-blur-xl md:p-8 ${className}`}
    >
      {/* Drag-and-drop area */}
      <motion.div
        variants={dropZoneVariants}
        animate={dragActive ? "active" : "idle"}
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`rounded-2xl border-2 border-dashed p-8 text-center transition ${
          dragActive
            ? "border-cyan-400 bg-cyan-500/10"
            : "border-white/20 bg-white/[0.03] hover:border-white/35"
        }`}
      >
        <motion.div whileHover={{ scale: 1.03 }} className="mx-auto mb-4 w-fit rounded-xl bg-gradient-to-br from-blue-600 to-violet-600 p-3">
          <UploadCloud className="size-7 text-white" />
        </motion.div>
        <p className="text-lg font-semibold text-white">
          Drop datasets here or click the buttons below
        </p>
        <p className="mt-2 text-sm text-slate-300">
          Supports CSV, Folder upload, and ZIP upload
        </p>
      </motion.div>

      {/* Hidden inputs */}
      <input
        ref={dataset1InputRef}
        type="file"
        accept=".csv,.zip"
        className="hidden"
        onChange={(e) => assignFixedSlot(0, e.target.files?.[0] ?? null)}
      />
      <input
        ref={dataset2InputRef}
        type="file"
        accept=".csv,.zip"
        className="hidden"
        onChange={(e) => assignFixedSlot(1, e.target.files?.[0] ?? null)}
      />
      <input
        ref={addMoreInputRef}
        type="file"
        accept=".csv,.zip"
        multiple
        className="hidden"
        onChange={(e) => addFilesToSlots(Array.from(e.target.files ?? []), true)}
      />
      <input
        ref={folderInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => addFilesToSlots(Array.from(e.target.files ?? []), false)}
      />

      {/* Controls and badges */}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          onClick={() => dataset1InputRef.current?.click()}
          className="inline-flex h-10 items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-4 text-sm font-semibold text-white transition hover:scale-[1.02]"
          type="button"
        >
          <Plus className="size-4" />
          Add Dataset 1
        </button>
        <button
          onClick={() => dataset2InputRef.current?.click()}
          className="inline-flex h-10 items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-4 text-sm font-semibold text-white transition hover:scale-[1.02]"
          type="button"
        >
          <Plus className="size-4" />
          Add Dataset 2
        </button>
        <button
          onClick={() => addMoreInputRef.current?.click()}
          disabled={!canAddMore}
          className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/20 bg-white/5 text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
          type="button"
          aria-label="Add more datasets"
        >
          <Plus className="size-5" />
        </button>
        <button
          onClick={() => folderInputRef.current?.click()}
          className="text-xs text-cyan-300 underline underline-offset-2 hover:text-cyan-200"
          type="button"
        >
          Upload Folder
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-slate-200">
          {MIN_REQUIRED} Datasets Required
        </span>
        <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-slate-200">
          Max 4 Datasets
        </span>
      </div>

      {/* Selected datasets */}
      <div className="mt-5 space-y-3">
        {datasets.map((file, index) =>
          file ? (
            <div
              key={`${index}-${fileKey(file)}`}
              className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3"
            >
              <div className="flex min-w-0 items-center gap-3">
                <FileText className="size-5 shrink-0 text-cyan-300" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-white">
                    Dataset {index + 1}: {file.name}
                  </p>
                  <p className="text-xs text-slate-400">{formatSize(file.size)}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => removeDataset(index)}
                className="rounded-lg p-1.5 text-slate-300 hover:bg-red-500/20 hover:text-red-200"
              >
                <X className="size-4" />
              </button>
            </div>
          ) : null
        )}
      </div>

      {/* Feedback messages */}
      {error && (
        <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}
      {successMsg && (
        <div className="mt-4 flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          <CheckCircle2 className="size-4" />
          {successMsg}
        </div>
      )}

      {/* Primary action */}
      <button
        type="button"
        onClick={handleUpload}
        disabled={loading}
        className="mt-6 inline-flex w-full items-center justify-center rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-blue-950/40 transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? (
          <>
            <Loader2 className="mr-2 size-5 animate-spin" />
            Uploading...
          </>
        ) : (
          <>
            <Sparkles className="mr-2 size-5" />
            Analyze Dataset with AI
          </>
        )}
      </button>
    </motion.section>
  );
}
