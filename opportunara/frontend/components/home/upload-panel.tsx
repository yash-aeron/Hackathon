"use client";

import {
  useEffect,
  useRef,
  useState,
  type DragEvent,
  type FormEvent,
} from "react";
import { Icon } from "@/components/icons";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { normalizeProfile } from "@/lib/profile";
import type { ParseProfileInput, ParsedProfileResult } from "@/lib/types";
import { buttonClass, CARD_CLASS, INPUT_CLASS, LABEL_CLASS } from "@/lib/ui";
import { cn, errorMessage } from "@/lib/utils";

type UploadTab = "file" | "text";

const PARSE_STAGES = [
  "Reading your resume…",
  "Extracting education, skills & projects…",
  "Verifying opportunity eligibility…",
];

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MIN_TEXT_LENGTH = 40;

interface UploadPanelProps {
  onParsed: (result: ParsedProfileResult) => void;
  compact?: boolean;
}

export function UploadPanel({ onParsed, compact = false }: UploadPanelProps) {
  const [tab, setTab] = useState<UploadTab>("file");
  const [text, setText] = useState("");
  const [lastFile, setLastFile] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [stage, setStage] = useState(0);
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const stageTimer = useRef<number | null>(null);
  const toast = useToast();

  useEffect(
    () => () => {
      if (stageTimer.current !== null) window.clearInterval(stageTimer.current);
    },
    [],
  );

  function startStages(label: string | null) {
    setBusy(true);
    setError(null);
    setBusyLabel(label);
    setStage(0);
    if (stageTimer.current !== null) window.clearInterval(stageTimer.current);
    stageTimer.current = window.setInterval(() => {
      setStage((current) =>
        current < PARSE_STAGES.length - 1 ? current + 1 : current,
      );
    }, 1400);
  }

  function stopStages() {
    if (stageTimer.current !== null) {
      window.clearInterval(stageTimer.current);
      stageTimer.current = null;
    }
    setStage(PARSE_STAGES.length - 1);
    setBusy(false);
    setBusyLabel(null);
  }

  function emitProfile(
    result: ParsedProfileResult,
    toastCopy: { title: string; description: string },
  ) {
    stopStages();
    onParsed(result);
    toast({ kind: "success", ...toastCopy });
  }

  async function runParse(input: ParseProfileInput, displayName: string) {
    startStages(displayName);
    try {
      const response = await api.parseProfile(input);
      const profile = normalizeProfile(response.profile);
      emitProfile(
        {
          profile,
          aiAvailable: response.ai_available,
          note: response.note,
          origin: response.source,
        },
        {
          title: "Profile extracted successfully",
          description: `Discovered ${profile.skills.length} skills and ${profile.projects.length} projects. Review and tweak them below.`,
        },
      );
    } catch (caught) {
      stopStages();
      const message = errorMessage(
        caught,
        "We couldn't parse that resume. Try pasting the text instead.",
      );
      setError(message);
      toast({ kind: "error", title: "Parsing failed", description: message });
    }
  }

  function handleFile(file: File) {
    const isPdf =
      file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      toast({
        kind: "error",
        title: "Please provide a PDF file",
        description: "Scoutly requires a standard PDF resume, or you can paste the text directly.",
      });
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      toast({
        kind: "error",
        title: "File exceeds 10 MB",
        description: "Please upload a compressed PDF under 10 MB.",
      });
      return;
    }
    setLastFile(file.name);
    void runParse({ kind: "file", file }, file.name);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  function handleTextSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = text.trim();
    if (trimmed.length < MIN_TEXT_LENGTH) {
      toast({
        kind: "error",
        title: "More content needed",
        description: `Please enter at least ${MIN_TEXT_LENGTH} characters.`,
      });
      return;
    }
    void runParse({ kind: "text", text: trimmed }, "pasted resume text");
  }

  async function handleSample() {
    startStages("Loading sample candidate profile…");
    try {
      const sample = await api.sampleResume();
      try {
        const response = await api.parseProfile({
          kind: "text",
          text: sample.text,
        });
        const profile = normalizeProfile(response.profile);
        emitProfile(
          {
            profile,
            aiAvailable: response.ai_available,
            note: response.note,
            origin: "sample",
          },
          {
            title: "Candidate Profile Loaded",
            description: `Loaded Yash Aeron (Graphic Era University, B.Tech CS) with ${profile.skills.length} skills and ${profile.projects.length} projects.`,
          },
        );
      } catch {
        emitProfile(
          {
            profile: normalizeProfile(sample.profile),
            aiAvailable: false,
            note: "Live extraction fallback used.",
            origin: "sample",
          },
          {
            title: "Sample profile loaded",
            description: "Sample profile loaded directly.",
          },
        );
      }
    } catch (caught) {
      stopStages();
      const message = errorMessage(
        caught,
        "Couldn't load sample profile. Make sure the backend is running.",
      );
      setError(message);
      toast({ kind: "error", title: "Sample unavailable", description: message });
    }
  }

  const canSubmitText = text.trim().length >= MIN_TEXT_LENGTH;

  return (
    <section
      className={cn(
        CARD_CLASS,
        compact ? "p-5" : "p-6 sm:p-8",
        "relative overflow-hidden"
      )}
    >
      <header className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex size-7 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Icon name="upload" className="size-4" />
            </span>
            <h2 className="font-display text-xl font-bold tracking-tight text-slate-900">
              {compact ? "Replace Resume" : "Upload Candidate Resume"}
            </h2>
          </div>
          <p className="text-xs leading-relaxed text-slate-500">
            {compact
              ? "Upload a revised PDF or paste new text to re-calculate your ranked matches."
              : "Upload your PDF or paste text. Scoutly extracts your credentials client-side with 0 server tracking."}
          </p>
        </div>
        <span className="self-start sm:self-center inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600 shadow-2xs">
          <Icon name="shield" className="size-3.5 text-emerald-600" />
          Zero Data Retention
        </span>
      </header>

      {busy ? (
        <ParseProgress stage={stage} busyLabel={busyLabel} />
      ) : (
        <>
          <div
            role="tablist"
            aria-label="Resume input method"
            className="mb-5 flex rounded-xl bg-slate-100 p-1 border border-slate-200"
          >
            <button
              type="button"
              role="tab"
              id="tab-file"
              aria-selected={tab === "file"}
              aria-controls="panel-file"
              tabIndex={tab === "file" ? 0 : -1}
              onClick={() => setTab("file")}
              className={cn(
                "flex-1 rounded-lg py-2 text-xs font-bold transition-[background-color,color,box-shadow]",
                tab === "file"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900",
              )}
            >
              Upload PDF
            </button>
            <button
              type="button"
              role="tab"
              id="tab-text"
              aria-selected={tab === "text"}
              aria-controls="panel-text"
              tabIndex={tab === "text" ? 0 : -1}
              onClick={() => setTab("text")}
              className={cn(
                "flex-1 rounded-lg py-2 text-xs font-bold transition-[background-color,color,box-shadow]",
                tab === "text"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900",
              )}
            >
              Paste Text
            </button>
          </div>

          {tab === "file" ? (
            <div
              role="tabpanel"
              id="panel-file"
              aria-labelledby="tab-file"
              onDragEnter={(event) => {
                event.preventDefault();
                setDragActive(true);
              }}
              onDragOver={(event) => {
                event.preventDefault();
                setDragActive(true);
              }}
              onDragLeave={(event) => {
                event.preventDefault();
                setDragActive(false);
              }}
              onDrop={handleDrop}
              className={cn(
                "group relative rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-all duration-200 cursor-pointer",
                dragActive
                  ? "border-blue-600 bg-blue-50/60 scale-[1.01]"
                  : "border-slate-300 hover:border-blue-500 hover:bg-slate-50/60 bg-slate-50/30",
              )}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                id="resume-file"
                type="file"
                accept=".pdf,application/pdf"
                className="sr-only"
                aria-label="Choose a PDF resume"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) handleFile(file);
                  event.target.value = "";
                }}
              />
              <div className="flex flex-col items-center gap-3">
                <span className="inline-flex size-14 items-center justify-center rounded-2xl border border-slate-200 bg-white text-blue-600 shadow-sm transition-transform group-hover:scale-110">
                  <Icon name="file" className="size-7" />
                </span>
                <div>
                  <p className="text-sm font-bold text-slate-900">
                    Drop your resume here, or <span className="text-blue-600 underline">browse files</span>
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Standard PDF · Up to 10 MB · Text-based PDF recommended
                  </p>
                </div>
                {lastFile && (
                  <span className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
                    <Icon name="checkCircle" className="size-3.5" />
                    Selected: {lastFile}
                  </span>
                )}
              </div>
            </div>
          ) : (
            <form
              role="tabpanel"
              id="panel-text"
              aria-labelledby="tab-text"
              onSubmit={handleTextSubmit}
              className="space-y-4"
            >
              <div>
                <label htmlFor="resume-text" className={LABEL_CLASS}>
                  Resume Content
                </label>
                <textarea
                  id="resume-text"
                  rows={8}
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder="Paste your resume sections here: Education, Technical Skills, Projects, Experience, and Certifications..."
                  className={cn(INPUT_CLASS, "resize-y leading-relaxed font-sans text-xs")}
                />
                <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                  <span>Minimum {MIN_TEXT_LENGTH} characters required</span>
                  <span className={cn(canSubmitText ? "text-emerald-600 font-semibold" : "text-slate-400")}>
                    {text.trim().length} chars
                  </span>
                </div>
              </div>
              <button
                type="submit"
                disabled={!canSubmitText}
                className={buttonClass("primary", "w-full")}
              >
                <Icon name="sparkles" className="size-4" />
                Extract Resume Profile
              </button>
            </form>
          )}

          <div className="my-6 flex items-center gap-4" aria-hidden="true">
            <span className="h-px flex-1 bg-slate-200" />
            <span className="text-[11px] font-bold tracking-wider text-slate-400 uppercase">
              or test drive instantly
            </span>
            <span className="h-px flex-1 bg-slate-200" />
          </div>

          <button
            type="button"
            onClick={() => void handleSample()}
            className="group flex w-full items-center justify-between rounded-xl border border-blue-200 bg-gradient-to-r from-blue-50/80 to-indigo-50/80 p-3.5 text-left transition-all hover:border-blue-300 hover:shadow-xs active:scale-[0.99]"
          >
            <div className="flex items-center gap-3">
              <span className="inline-flex size-9 items-center justify-center rounded-lg bg-blue-600 text-white shadow-xs">
                <Icon name="cap" className="size-5" />
              </span>
              <div>
                <p className="text-xs font-bold text-slate-900 group-hover:text-blue-700">
                  Load Pre-Built Sample Profile
                </p>
                <p className="text-[11px] text-slate-500">
                  Yash Aeron · B.Tech CS, Graphic Era University (Python, FastAPI, TypeScript, React)
                </p>
              </div>
            </div>
            <Icon name="arrowRight" className="size-4 text-blue-600 transition-transform group-hover:translate-x-1" />
          </button>

          {error && (
            <p role="alert" className="mt-4 text-xs font-medium text-rose-600">
              {error}
            </p>
          )}
        </>
      )}
    </section>
  );
}

function ParseProgress({
  stage,
  busyLabel,
}: {
  stage: number;
  busyLabel: string | null;
}) {
  return (
    <div className="rounded-2xl border border-blue-200 bg-blue-50/40 p-8 text-center animate-fade-up">
      <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-md shadow-blue-500/20">
        <Icon name="sparkles" className="size-7 animate-spin" />
      </div>

      <h3 className="mt-4 font-display text-lg font-bold text-slate-900">
        {busyLabel ?? "Processing your resume…"}
      </h3>

      <div className="mx-auto mt-6 max-w-sm space-y-3 text-left">
        {PARSE_STAGES.map((label, index) => {
          const done = index < stage;
          const current = index === stage;
          return (
            <div
              key={label}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2 text-xs transition-colors",
                current
                  ? "bg-white font-bold text-blue-700 shadow-xs"
                  : done
                    ? "text-emerald-700 font-semibold"
                    : "text-slate-400 font-normal",
              )}
            >
              <span
                className={cn(
                  "inline-flex size-5 items-center justify-center rounded-full border text-[10px]",
                  done
                    ? "border-emerald-500 bg-emerald-500 text-white"
                    : current
                      ? "border-blue-600 bg-blue-600 text-white animate-pulse"
                      : "border-slate-300 bg-white",
                )}
              >
                {done ? <Icon name="check" className="size-3" /> : index + 1}
              </span>
              <span>{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
