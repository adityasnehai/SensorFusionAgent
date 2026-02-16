"use client";

import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import {
  Upload,
  Database,
  ChevronRight,
  FileText,
  Sparkles,
  Brain,
  Zap,
  BarChart3,
  Plus,
} from "lucide-react";
import { motion } from "motion/react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import type { FuseJobCreateResponse, FuseResponse } from "../types/fusion";

const MIN_DATASETS = 2;
const MAX_DATASETS = 4;
const FUSE_API_URL = process.env.NEXT_PUBLIC_FUSE_API_URL ?? "http://localhost:8000/fuse";
const PARTICLE_COUNT = 20;

interface HeroProps {
  onUploadSuccess?: (result: FuseResponse) => void;
  onJobCreated?: (job: FuseJobCreateResponse) => void;
  onUploadError?: (message: string) => void;
  onUploadStateChange?: (loading: boolean) => void;
}

interface DatasetSelection {
  files: File[];
  kind: "file";
  label: string;
  totalSize: number;
}

function seededValue(seed: number) {
  const raw = Math.sin(seed * 12.9898) * 43758.5453;
  return raw - Math.floor(raw);
}

const PARTICLES = Array.from({ length: PARTICLE_COUNT }, (_, index) => {
  const base = index + 1;
  return {
    left: `${(seededValue(base) * 92 + 4).toFixed(4)}%`,
    top: `${(seededValue(base + 97) * 92 + 4).toFixed(4)}%`,
    duration: 3 + seededValue(base + 173) * 2,
    delay: seededValue(base + 257) * 2,
  };
});

function fileKey(file: File) {
  return `${file.name}-${file.size}-${file.lastModified}`;
}

function buildFileSelection(file: File): DatasetSelection {
  return {
    files: [file],
    kind: "file",
    label: file.name,
    totalSize: file.size,
  };
}

export function Hero({
  onUploadSuccess,
  onJobCreated,
  onUploadError,
  onUploadStateChange,
}: HeroProps) {
  const [dragActive, setDragActive] = useState(false);
  const [dataset1, setDataset1] = useState<DatasetSelection | null>(null);
  const [dataset2, setDataset2] = useState<DatasetSelection | null>(null);
  const [extraFiles, setExtraFiles] = useState<DatasetSelection[]>([]);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const dataset1InputRef = useRef<HTMLInputElement | null>(null);
  const dataset2InputRef = useRef<HTMLInputElement | null>(null);
  const extraInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  const collectExisting = (
    nextDataset1: DatasetSelection | null,
    nextDataset2: DatasetSelection | null,
    nextExtraFiles: DatasetSelection[]
  ) =>
    [nextDataset1, nextDataset2, ...nextExtraFiles]
      .filter(Boolean)
      .flatMap((entry) => (entry ? entry.files : []));

  const addFiles = (incoming: File[]) => {
    if (!incoming.length) return;

    let nextDataset1 = dataset1;
    let nextDataset2 = dataset2;
    const nextExtraFiles = [...extraFiles];
    let rejected = false;

    for (const file of incoming) {
      const exists = collectExisting(
        nextDataset1,
        nextDataset2,
        nextExtraFiles
      ).some((item) => fileKey(item) === fileKey(file));
      if (exists) continue;

      if (!nextDataset1) {
        nextDataset1 = buildFileSelection(file);
        continue;
      }
      if (!nextDataset2) {
        nextDataset2 = buildFileSelection(file);
        continue;
      }
      if (nextExtraFiles.length < MAX_DATASETS - MIN_DATASETS) {
        nextExtraFiles.push(buildFileSelection(file));
      } else {
        rejected = true;
      }
    }

    setDataset1(nextDataset1);
    setDataset2(nextDataset2);
    setExtraFiles(nextExtraFiles);
    setStatus(null);

    if (rejected) {
      const message = `Maximum ${MAX_DATASETS} datasets allowed.`;
      setError(message);
      onUploadError?.(message);
    } else if (nextDataset1 && nextDataset2) {
      setError(null);
    }
  };

  const handleDataset1Change = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setDataset1(file ? buildFileSelection(file) : null);
    setStatus(null);
    if (file && dataset2) {
      setError(null);
    }
    e.target.value = "";
  };

  const handleDataset2Change = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setDataset2(file ? buildFileSelection(file) : null);
    setStatus(null);
    if (file && dataset1) {
      setError(null);
    }
    e.target.value = "";
  };

  const handleExtraFilesChange = (e: ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(e.target.files ?? []));
    e.target.value = "";
  };

  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    addFiles(Array.from(e.dataTransfer.files));
  };

  const removeDataset1 = () => {
    setDataset1(null);
    setStatus(null);
  };
  const removeDataset2 = () => {
    setDataset2(null);
    setStatus(null);
  };
  const removeExtraFile = (index: number) => {
    setExtraFiles((prev) => prev.filter((_, i) => i !== index));
    setStatus(null);
  };

  const canAnalyze = Boolean(dataset1 && dataset2);
  const canAddMore = Boolean(MAX_DATASETS - MIN_DATASETS - extraFiles.length > 0);

  const appendDatasetSelection = (
    formData: FormData,
    singleKey: string,
    selection: DatasetSelection
  ) => {
    formData.append(singleKey, selection.files[0]);
  };

  const handleAnalyze = async () => {
    if (!dataset1 || !dataset2) {
      const message = "Dataset 1 and Dataset 2 are required.";
      setError(message);
      onUploadError?.(message);
      return;
    }

    setError(null);
    setStatus(null);
    setLoading(true);
    onUploadStateChange?.(true);

    try {
      const formData = new FormData();
      appendDatasetSelection(formData, "dataset1", dataset1);
      appendDatasetSelection(formData, "dataset2", dataset2);
      if (extraFiles[0]) {
        appendDatasetSelection(formData, "dataset3", extraFiles[0]);
      }
      if (extraFiles[1]) {
        appendDatasetSelection(formData, "dataset4", extraFiles[1]);
      }

      const response = await fetch(FUSE_API_URL, {
        method: "POST",
        body: formData,
      });

      const responseText = await response.text();
      let payload: Record<string, unknown>;
      try {
        payload = responseText ? JSON.parse(responseText) : {};
      } catch {
        payload = {};
      }

      if (!response.ok) {
        const detail =
          typeof payload.message === "string"
            ? payload.message
            : typeof payload.detail === "string"
              ? payload.detail
              : "Fusion failed.";
        throw new Error(detail);
      }

      if (typeof payload.job_id === "string") {
        const job: FuseJobCreateResponse = {
          job_id: payload.job_id,
          status: typeof payload.status === "string" ? payload.status : "processing",
        };
        onJobCreated?.(job);
        setStatus(`Fusion job queued: ${job.job_id.slice(0, 8)}...`);
      } else {
        const result = payload as FuseResponse;
        onUploadSuccess?.(result);
        setStatus(
          `Fusion complete. HQScore: ${
            typeof result.hqscore === "number"
              ? result.hqscore.toFixed(4)
              : result.hqscore
          }`
        );
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Fusion failed.";
      setError(message);
      onUploadError?.(message);
    } finally {
      setLoading(false);
      onUploadStateChange?.(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white overflow-hidden relative">
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#4f4f4f12_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f12_1px,transparent_1px)] bg-[size:64px_64px]" />

      <motion.div
        className="absolute top-0 left-1/4 w-96 h-96 bg-blue-600/20 rounded-full blur-3xl"
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{
          duration: 8,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      <motion.div
        className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl"
        animate={{
          scale: [1, 1.3, 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{
          duration: 10,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      <motion.div
        className="absolute top-1/2 left-1/2 w-96 h-96 bg-cyan-600/15 rounded-full blur-3xl"
        animate={{
          scale: [1, 1.4, 1],
          opacity: [0.2, 0.4, 0.2],
        }}
        transition={{
          duration: 12,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />

      {PARTICLES.map((particle, i) => (
        <motion.div
          key={i}
          className="absolute w-1 h-1 bg-blue-400/40 rounded-full"
          style={{
            left: particle.left,
            top: particle.top,
          }}
          animate={{
            y: [0, -30, 0],
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: particle.duration,
            repeat: Infinity,
            delay: particle.delay,
          }}
        />
      ))}

      <motion.div
        className="fixed w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none"
        animate={{
          x: mousePosition.x - 192,
          y: mousePosition.y - 192,
        }}
        transition={{
          type: "spring",
          damping: 30,
          stiffness: 200,
        }}
      />

      <header className="relative z-10 px-6 py-6 border-b border-white/5 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto flex items-center">
          <motion.div
            className="flex items-center gap-3"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="relative">
              <div className="absolute inset-0 bg-blue-500/20 blur-xl rounded-full" />
              <Brain className="size-8 text-blue-400 relative" />
            </div>
            <span className="text-2xl font-bold bg-gradient-to-r from-blue-400 via-cyan-400 to-purple-400 bg-clip-text text-transparent">
              DataSenseAgent
            </span>
          </motion.div>
        </div>
      </header>

      <main className="relative z-10 px-6 py-16 md:py-24">
        <div className="max-w-6xl mx-auto">
          <motion.div
            className="text-center mb-12"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <motion.div
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500/10 border border-blue-500/20 text-blue-400 rounded-full text-sm mb-6 backdrop-blur-sm"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              <Sparkles className="size-4" />
              IMU Sensor Data Harmonization Agent
            </motion.div>

            <motion.h1
              className="text-5xl md:text-6xl lg:text-7xl font-bold mb-6"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
            >
              <span className="text-white">IMU Sensor Data</span>
              <br />
              <span className="bg-gradient-to-r from-blue-400 via-cyan-400 to-purple-400 bg-clip-text text-transparent">
                Harmonization Agent
              </span>
            </motion.h1>

            <motion.p
              className="text-xl text-gray-400 max-w-3xl mx-auto mb-8"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
            >
              Process IMU accelerometer, gyroscope, magnetometer, and GPS
              modalities with synchronized fusion-ready alignment.
            </motion.p>

            <motion.div
              className="flex items-center justify-center gap-8 mb-12"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.5 }}
            >
              <div className="text-center">
                <div className="text-3xl font-bold text-white mb-1">
                  {MIN_DATASETS}
                </div>
                <div className="text-sm text-gray-500">Minimum Datasets</div>
              </div>
              <div className="w-px h-12 bg-white/10" />
              <div className="text-center">
                <div className="text-3xl font-bold text-white mb-1">
                  {MAX_DATASETS}
                </div>
                <div className="text-sm text-gray-500">Maximum Datasets</div>
              </div>
              <div className="w-px h-12 bg-white/10" />
              <div className="text-center">
                <div className="text-3xl font-bold text-white mb-1">
                  {"<"}5s
                </div>
                <div className="text-sm text-gray-500">Processing Time</div>
              </div>
            </motion.div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.6 }}
          >
            <Card className="max-w-3xl mx-auto p-8 bg-white/5 backdrop-blur-xl shadow-2xl border border-white/10 relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-r from-blue-600/10 via-purple-600/10 to-cyan-600/10" />

              <div className="relative z-10">
                <div
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  className={`relative border-2 border-dashed rounded-xl p-12 transition-all ${
                    dragActive
                      ? "border-blue-500 bg-blue-500/10"
                      : "border-white/20 hover:border-white/30 hover:bg-white/5"
                  }`}
                >
                  <input
                    type="file"
                    id="dataset-1-upload"
                    ref={dataset1InputRef}
                    className="hidden"
                    onChange={handleDataset1Change}
                    accept=".csv,.zip"
                  />
                  <input
                    type="file"
                    id="dataset-2-upload"
                    ref={dataset2InputRef}
                    className="hidden"
                    onChange={handleDataset2Change}
                    accept=".csv,.zip"
                  />
                  <input
                    type="file"
                    id="dataset-extra-upload"
                    ref={extraInputRef}
                    className="hidden"
                    onChange={handleExtraFilesChange}
                    accept=".csv,.zip"
                    multiple
                  />

                  <div className="flex flex-col items-center justify-center text-center">
                    <motion.div
                      className="p-4 bg-gradient-to-br from-blue-600 to-purple-600 rounded-2xl mb-4 relative"
                      whileHover={{ scale: 1.05 }}
                      transition={{
                        type: "spring",
                        stiffness: 400,
                        damping: 10,
                      }}
                    >
                      <div className="absolute inset-0 bg-gradient-to-br from-blue-400 to-purple-400 rounded-2xl blur-xl opacity-50" />
                      <Upload className="size-8 text-white relative" />
                    </motion.div>

                    <h3 className="text-xl font-semibold text-white mb-2">
                      Drop datasets here or click to browse
                    </h3>
                    <p className="text-gray-400 text-center mb-4">Supports CSV and ZIP files</p>

                    <div className="mb-5 flex w-full max-w-3xl items-center gap-3">
                      <div className="flex w-full flex-1 items-center gap-2">
                        <Button
                          type="button"
                          onClick={() => dataset1InputRef.current?.click()}
                          className="w-full flex-1 justify-center bg-gradient-to-r from-blue-600 to-purple-600 shadow-lg shadow-blue-500/25 hover:from-blue-500 hover:to-purple-500"
                        >
                          <Plus className="size-4 shrink-0" />
                          <span className="leading-none">Add Dataset 1</span>
                        </Button>
                      </div>
                      <div className="flex w-full flex-1 items-center gap-2">
                        <Button
                          type="button"
                          onClick={() => dataset2InputRef.current?.click()}
                          className="w-full flex-1 justify-center bg-gradient-to-r from-blue-600 to-purple-600 shadow-lg shadow-blue-500/25 hover:from-blue-500 hover:to-purple-500"
                        >
                          <Plus className="size-4 shrink-0" />
                          <span className="leading-none">Add Dataset 2</span>
                        </Button>
                      </div>
                      <Button
                        type="button"
                        onClick={() => extraInputRef.current?.click()}
                        variant="outline"
                        disabled={!canAddMore}
                        className="h-10 w-10 justify-center border-white/20 bg-white/5 p-0 text-white hover:bg-white/10"
                        aria-label="Add more datasets"
                      >
                        <Plus className="size-5 shrink-0" />
                      </Button>
                    </div>

                    <div className="flex items-center gap-3 mb-3">
                      <div className="flex items-center gap-2 px-3 py-1.5 bg-white/5 rounded-full border border-white/10">
                        <Zap className="size-4 text-yellow-400" />
                        <span className="text-xs text-gray-300">
                          2 Datasets Required
                        </span>
                      </div>
                      <div className="flex items-center gap-2 px-3 py-1.5 bg-white/5 rounded-full border border-white/10">
                        <Brain className="size-4 text-blue-400" />
                        <span className="text-xs text-gray-300">
                          Max {MAX_DATASETS} Datasets
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {(dataset1 || dataset2 || extraFiles.length > 0) && (
                  <motion.div
                    className="space-y-3 mt-4"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3 }}
                  >
                    {dataset1 && (
                      <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-4 flex-1 min-w-0">
                            <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                              <FileText className="size-6 text-blue-400 flex-shrink-0" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <h4 className="font-semibold text-white mb-1 truncate">
                                Dataset 1: {dataset1.label}
                              </h4>
                              <p className="text-sm text-gray-400">
                                {(dataset1.totalSize / 1024).toFixed(2)} KB
                              </p>
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={removeDataset1}
                            className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                          >
                            Remove
                          </Button>
                        </div>
                      </div>
                    )}

                    {dataset2 && (
                      <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-4 flex-1 min-w-0">
                            <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                              <FileText className="size-6 text-blue-400 flex-shrink-0" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <h4 className="font-semibold text-white mb-1 truncate">
                                Dataset 2: {dataset2.label}
                              </h4>
                              <p className="text-sm text-gray-400">
                                {(dataset2.totalSize / 1024).toFixed(2)} KB
                              </p>
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={removeDataset2}
                            className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                          >
                            Remove
                          </Button>
                        </div>
                      </div>
                    )}

                    {extraFiles.map((selection, index) => (
                      <div
                        key={selection.files.map(fileKey).join("|")}
                        className="bg-white/5 rounded-lg p-4 border border-white/10"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-4 flex-1 min-w-0">
                            <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                              <FileText className="size-6 text-blue-400 flex-shrink-0" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <h4 className="font-semibold text-white mb-1 truncate">
                                Dataset {index + 3}: {selection.label}
                              </h4>
                              <p className="text-sm text-gray-400">
                                {(selection.totalSize / 1024).toFixed(2)} KB
                              </p>
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeExtraFile(index)}
                            className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                          >
                            Remove
                          </Button>
                        </div>
                      </div>
                    ))}
                  </motion.div>
                )}

                {error && (
                  <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                    {error}
                  </div>
                )}
                {status && (
                  <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
                    {status}
                  </div>
                )}

                <Button
                  type="button"
                  onClick={handleAnalyze}
                  className="w-full mt-5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 shadow-lg shadow-blue-500/25 disabled:opacity-40 disabled:cursor-not-allowed"
                  size="lg"
                  disabled={!canAnalyze || loading}
                >
                  <Sparkles className="mr-2 size-5" />
                  {loading ? "Analyzing..." : "Analyze Dataset with AI"}
                  <ChevronRight className="ml-2 size-5" />
                </Button>
              </div>
            </Card>
          </motion.div>

          <motion.div
            id="features"
            className="grid md:grid-cols-3 gap-6 mt-16 max-w-5xl mx-auto"
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.8 }}
          >
            <Card className="p-6 bg-white/5 backdrop-blur-xl border border-white/10 hover:border-white/20 transition-all group">
              <motion.div
                className="p-3 bg-gradient-to-br from-purple-600/20 to-purple-600/10 rounded-xl w-fit mb-4 border border-purple-500/20"
                whileHover={{ scale: 1.05 }}
              >
                <Database className="size-6 text-purple-400" />
              </motion.div>
              <h3 className="font-semibold text-white mb-2">
                Multi-Format Support
              </h3>
              <p className="text-gray-400 text-sm">
                Supports CSV files, data folders, and ZIP archives for
                multi-modal processing.
              </p>
            </Card>

            <Card className="p-6 bg-white/5 backdrop-blur-xl border border-white/10 hover:border-white/20 transition-all group">
              <motion.div
                className="p-3 bg-gradient-to-br from-blue-600/20 to-blue-600/10 rounded-xl w-fit mb-4 border border-blue-500/20"
                whileHover={{ scale: 1.05 }}
              >
                <BarChart3 className="size-6 text-blue-400" />
              </motion.div>
              <h3 className="font-semibold text-white mb-2">
                AI-Powered Insights
              </h3>
              <p className="text-gray-400 text-sm">
                Advanced machine learning algorithms extract patterns and
                generate actionable insights.
              </p>
            </Card>

            <Card className="p-6 bg-white/5 backdrop-blur-xl border border-white/10 hover:border-white/20 transition-all group">
              <motion.div
                className="p-3 bg-gradient-to-br from-green-600/20 to-green-600/10 rounded-xl w-fit mb-4 border border-green-500/20"
                whileHover={{ scale: 1.05 }}
              >
                <Zap className="size-6 text-green-400" />
              </motion.div>
              <h3 className="font-semibold text-white mb-2">Lightning Fast</h3>
              <p className="text-gray-400 text-sm">
                Process and analyze millions of rows in seconds with our
                optimized infrastructure.
              </p>
            </Card>
          </motion.div>
        </div>
      </main>
    </div>
  );
}

export default Hero;
