"use client";

import { useState } from "react";
import { Icon } from "@/components/icons";
import { CopyButton } from "@/components/ui/copy-button";
import { AiUnavailableNotice } from "@/components/ui/notices";
import type { KitResponse } from "@/lib/types";
import { CARD_CLASS, buttonClass } from "@/lib/ui";
import { cn } from "@/lib/utils";

type KitTab = "gaps" | "bullets" | "note";

const TABS: Array<{ id: KitTab; label: string; icon: "target" | "file" | "sparkles" }> = [
  { id: "gaps", label: "Gap Analysis & Roadmap", icon: "target" },
  { id: "bullets", label: "Tailored Resume Bullets", icon: "file" },
  { id: "note", label: "Cover Note & Pitch", icon: "sparkles" },
];

interface KitPanelProps {
  kit: KitResponse;
  regenerating: boolean;
  onRegenerate: () => void;
}

export function KitPanel({ kit, regenerating, onRegenerate }: KitPanelProps) {
  const [tab, setTab] = useState<KitTab>("gaps");

  return (
    <div className="space-y-6">
      {kit.ai_available === false && (
        <AiUnavailableNotice note={kit.note} />
      )}

      {/* Modern Segmented Navigation Tabs */}
      <div
        role="tablist"
        aria-label="Application kit sections"
        className="flex rounded-2xl bg-slate-100 p-1.5 border border-slate-200"
      >
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`kit-tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`kit-panel-${item.id}`}
            tabIndex={tab === item.id ? 0 : -1}
            onClick={() => setTab(item.id)}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 rounded-xl py-2.5 px-3 text-xs font-bold transition-all duration-150",
              tab === item.id
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900",
            )}
          >
            <Icon
              name={item.icon}
              className={cn(
                "size-4",
                tab === item.id ? "text-blue-600" : "text-slate-400",
              )}
            />
            <span className="hidden sm:inline">{item.label}</span>
            <span className="sm:hidden">
              {item.id === "gaps" ? "Roadmap" : item.id === "bullets" ? "Bullets" : "Note"}
            </span>
          </button>
        ))}
      </div>

      <div>
        {tab === "gaps" && <GapTab kit={kit} />}
        {tab === "bullets" && <BulletsTab kit={kit} />}
        {tab === "note" && (
          <NoteTab
            kit={kit}
            regenerating={regenerating}
            onRegenerate={onRegenerate}
          />
        )}
      </div>
    </div>
  );
}

function GapTab({ kit }: { kit: KitResponse }) {
  const { strengths, gaps, roadmap } = kit.gap_analysis;
  const [completedItems, setCompletedItems] = useState<Record<number, boolean>>({});

  function toggleItem(index: number) {
    setCompletedItems((current) => ({
      ...current,
      [index]: !current[index],
    }));
  }

  return (
    <div
      role="tabpanel"
      id="kit-panel-gaps"
      aria-labelledby="kit-tab-gaps"
      className="space-y-6 animate-fade-up"
    >
      {/* Strengths vs Gaps Comparison Grid */}
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Strengths */}
        <section className={cn(CARD_CLASS, "p-5 border-emerald-200/80 bg-emerald-50/20")}>
          <div className="flex items-center gap-2 text-emerald-800 font-display font-bold text-sm mb-3">
            <span className="flex size-6 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
              <Icon name="checkCircle" className="size-4" />
            </span>
            Profile Strengths for this Role
          </div>
          <ul className="space-y-2.5">
            {strengths.length === 0 ? (
              <li className="text-xs text-slate-500">
                Add more skills & projects to your profile to uncover strengths.
              </li>
            ) : (
              strengths.map((strength, index) => (
                <li
                  key={`${strength}-${index}`}
                  className="flex items-start gap-2 text-xs leading-relaxed text-slate-700"
                >
                  <Icon name="check" className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />
                  <span>{strength}</span>
                </li>
              ))
            )}
          </ul>
        </section>

        {/* Gaps */}
        <section className={cn(CARD_CLASS, "p-5 border-amber-200/80 bg-amber-50/20")}>
          <div className="flex items-center gap-2 text-amber-900 font-display font-bold text-sm mb-3">
            <span className="flex size-6 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
              <Icon name="alert" className="size-4" />
            </span>
            Targeted Skill Gaps
          </div>
          <ul className="space-y-2.5">
            {gaps.length === 0 ? (
              <li className="text-xs text-slate-500">
                No major skill gaps identified — your profile matches all essential requirements!
              </li>
            ) : (
              gaps.map((gap, index) => (
                <li
                  key={`${gap}-${index}`}
                  className="flex items-start gap-2 text-xs leading-relaxed text-slate-700"
                >
                  <span className="mt-1 size-1.5 shrink-0 rounded-full bg-amber-500" />
                  <span>{gap}</span>
                </li>
              ))
            )}
          </ul>
        </section>
      </div>

      {/* 3-Week Interactive Action Roadmap */}
      <section className={cn(CARD_CLASS, "p-6 sm:p-7")}>
        <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-100 pb-4 mb-6">
          <div>
            <h3 className="font-display text-base font-bold text-slate-900 flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                <Icon name="calendar" className="size-4" />
              </span>
              Personalized {roadmap.length}-Week Prep Roadmap
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Free, curated resources tailored to bridge identified skill gaps before interview rounds.
            </p>
          </div>
          <span className="self-start sm:self-auto inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
            Self-Paced Roadmap
          </span>
        </header>

        <ol className="relative space-y-6">
          {roadmap.map((week, index) => {
            const isCompleted = completedItems[index] ?? false;
            return (
              <li
                key={week.week}
                className={cn(
                  "relative rounded-2xl border p-5 transition-all",
                  isCompleted
                    ? "border-emerald-200 bg-emerald-50/30"
                    : "border-slate-200 bg-slate-50/50 hover:bg-slate-50",
                )}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2.5">
                  <div className="flex items-center gap-2.5">
                    <span className="inline-flex size-6 items-center justify-center rounded-lg bg-blue-600 text-white font-mono text-xs font-bold shadow-2xs">
                      W{week.week}
                    </span>
                    <h4 className="font-display text-sm font-bold text-slate-900">
                      Week {week.week}: Focus & Milestones
                    </h4>
                  </div>
                  <button
                    type="button"
                    onClick={() => toggleItem(index)}
                    className={cn(
                      "self-start sm:self-auto inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold border transition-all active:scale-[0.98]",
                      isCompleted
                        ? "border-emerald-300 bg-emerald-100 text-emerald-800"
                        : "border-slate-200 bg-white text-slate-600 hover:bg-slate-100",
                    )}
                  >
                    <Icon name={isCompleted ? "checkCircle" : "target"} className="size-3.5" />
                    <span>{isCompleted ? "Marked Complete" : "Mark as Done"}</span>
                  </button>
                </div>

                <p className="text-xs font-medium text-slate-700 leading-relaxed mb-3">
                  {week.goal}
                </p>

                {week.resources.length > 0 && (
                  <div className="border-t border-slate-200/60 pt-3">
                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-2">
                      Recommended Learning Resources:
                    </span>
                    <ul className="space-y-1.5">
                      {week.resources.map((resource) => (
                        <li
                          key={resource}
                          className="flex items-start gap-2 text-xs leading-relaxed text-slate-600"
                        >
                          <Icon
                            name="link"
                            className="mt-0.5 size-3.5 shrink-0 text-blue-500"
                          />
                          <span>{resource}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      </section>
    </div>
  );
}

function BulletsTab({ kit }: { kit: KitResponse }) {
  const bullets = kit.resume_bullets;

  return (
    <div
      role="tabpanel"
      id="kit-panel-bullets"
      aria-labelledby="kit-tab-bullets"
      className="space-y-6 animate-fade-up"
    >
      <section className={cn(CARD_CLASS, "p-6 sm:p-7")}>
        <header className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 border-b border-slate-100 pb-5 mb-5">
          <div>
            <h3 className="font-display text-base font-bold text-slate-900 flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                <Icon name="file" className="size-4" />
              </span>
              Tailored Resume Action Bullets
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">
              Formatted using Google XYZ structure (Accomplished [X], as measured by [Y], by doing [Z]).
            </p>
          </div>
          {bullets.length > 0 && (
            <CopyButton
              text={bullets.join("\n\n")}
              label="Copy All Bullets"
              className="self-start sm:self-auto"
            />
          )}
        </header>

        <ul className="space-y-3.5">
          {bullets.length === 0 ? (
            <li className="text-xs text-slate-500 p-4 rounded-xl border border-dashed border-slate-200 text-center">
              No bullets generated yet. Try regenerating from the next tab.
            </li>
          ) : (
            bullets.map((bullet, index) => (
              <li
                key={`${bullet}-${index}`}
                className="group flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50/50 p-4 transition-all hover:border-slate-300 hover:bg-slate-50"
              >
                <div className="flex items-start gap-3 min-w-0 flex-1">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-md bg-white border border-slate-200 font-mono text-[10px] font-bold text-slate-600 mt-0.5">
                    {index + 1}
                  </span>
                  <p className="text-xs leading-relaxed text-slate-800 font-medium">
                    {bullet}
                  </p>
                </div>
                <div className="self-end sm:self-center shrink-0">
                  <CopyButton text={bullet} label="Copy" />
                </div>
              </li>
            ))
          )}
        </ul>

        <div className="mt-5 rounded-xl border border-blue-100 bg-blue-50/50 p-3.5 text-xs text-blue-800 flex items-center gap-2.5">
          <Icon name="info" className="size-4 shrink-0 text-blue-600" />
          <span>
            Tip: Drop these bullets directly into your project achievements. Adjust numerical metrics to reflect your actual project scale.
          </span>
        </div>
      </section>
    </div>
  );
}

function NoteTab({
  kit,
  regenerating,
  onRegenerate,
}: {
  kit: KitResponse;
  regenerating: boolean;
  onRegenerate: () => void;
}) {
  const wordCount = kit.cover_note.trim()
    ? kit.cover_note.trim().split(/\s+/).filter(Boolean).length
    : 0;

  return (
    <div
      role="tabpanel"
      id="kit-panel-note"
      aria-labelledby="kit-tab-note"
      className="space-y-6 animate-fade-up"
    >
      <section className={cn(CARD_CLASS, "p-6 sm:p-7")}>
        <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-5 mb-5">
          <div>
            <h3 className="font-display text-base font-bold text-slate-900 flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                <Icon name="sparkles" className="size-4" />
              </span>
              High-Conversion Cold Email & Cover Note
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              {wordCount} words · Designed to be read in under 30 seconds by busy hiring managers.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <CopyButton text={kit.cover_note} label="Copy Email Note" />
            <button
              type="button"
              onClick={onRegenerate}
              disabled={regenerating}
              className={buttonClass("secondary", "px-3 py-1.5 text-xs font-semibold")}
            >
              {regenerating ? (
                <span
                  className="size-3.5 animate-spin rounded-full border-2 border-slate-400 border-t-slate-700"
                  aria-hidden="true"
                />
              ) : (
                <Icon name="refresh" className="size-3.5" />
              )}
              {regenerating ? "Rewriting…" : "Regenerate Draft"}
            </button>
          </div>
        </header>

        {/* Note body */}
        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-5 font-sans text-xs leading-relaxed text-slate-800 whitespace-pre-wrap selection:bg-blue-200">
          {kit.cover_note || "No cover note available. Click Regenerate to draft one."}
        </div>

        {/* One line elevator pitch */}
        {kit.why_me_one_liner && (
          <div className="mt-5 rounded-2xl border border-indigo-200 bg-gradient-to-r from-blue-50/80 to-indigo-50/80 p-4.5">
            <span className="text-[10px] font-bold tracking-wider text-blue-700 uppercase">
              30-Second Elevator Pitch
            </span>
            <p className="mt-1 font-display text-sm font-semibold text-slate-900 leading-snug">
              &ldquo;{kit.why_me_one_liner}&rdquo;
            </p>
            <div className="mt-3">
              <CopyButton
                text={kit.why_me_one_liner}
                label="Copy Elevator Pitch"
                className="bg-white"
              />
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
