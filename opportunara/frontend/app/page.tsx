"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Icon } from "@/components/icons";
import { ProfileEditor } from "@/components/home/profile-editor";
import { UploadPanel } from "@/components/home/upload-panel";
import { AiUnavailableNotice } from "@/components/ui/notices";
import { ProfileSkeleton } from "@/components/ui/skeleton";
import { isProfileUsable, profileReadiness } from "@/lib/profile";
import { clearStoredProfile, saveProfile } from "@/lib/storage";
import type { ParsedProfileResult, StudentProfile } from "@/lib/types";
import { CARD_CLASS, buttonClass } from "@/lib/ui";
import { useIsClient, useProfile } from "@/lib/use-stored";
import { cn, pluralize } from "@/lib/utils";

const HERO_STATS = [
  { value: "60+", label: "Verified Listings", icon: "checkCircle" as const },
  { value: "5", label: "Opportunity Types", icon: "zap" as const },
  { value: "4-Point", label: "Fit Scoring Signals", icon: "target" as const },
  { value: "100%", label: "Client-Side Privacy", icon: "shield" as const },
];

export default function HomePage() {
  const isClient = useIsClient();
  const stored = useProfile();
  const hasProfile = isClient && isProfileUsable(stored);

  return (
    <div className="relative overflow-hidden">
      {/* Background radial atmosphere */}
      <div
        className="hero-grid pointer-events-none absolute inset-x-0 top-0 h-[480px]"
        aria-hidden="true"
      />

      <section className="relative mx-auto max-w-6xl px-4 pt-12 pb-10 sm:px-6 sm:pt-16">
        <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50/80 px-3.5 py-1 text-xs font-semibold text-blue-800 shadow-2xs mb-5">
          <span className="size-2 rounded-full bg-blue-600 animate-pulse-dot" />
          Engineered for Indian Engineering & Tech Students
        </div>

        <h1 className="max-w-4xl font-display text-4xl sm:text-6xl font-extrabold tracking-tight text-slate-900 leading-[1.08]">
          Opportunities that{" "}
          <span className="bg-gradient-to-r from-blue-600 via-indigo-600 to-emerald-600 bg-clip-text text-transparent">
            actually match
          </span>{" "}
          your credentials.
        </h1>
        <p className="mt-4 max-w-2xl text-base sm:text-lg leading-relaxed text-slate-600">
          Upload your resume once. Scoutly cross-checks your skills against 60+ verified
          internships, hackathons and scholarships, exposes hidden risk signals, and drafts
          your tailored application kit.
        </p>

        <div className="mt-7 flex flex-wrap items-center gap-4">
          {hasProfile ? (
            <Link href="/matches" className={buttonClass("primary", "px-6 py-3 text-sm")}>
              View Your Ranked Matches
              <Icon name="arrowRight" className="size-4" />
            </Link>
          ) : (
            <a href="#intake-workspace" className={buttonClass("primary", "px-6 py-3 text-sm")}>
              Start Intake (Drag & Drop PDF)
              <Icon name="arrowRight" className="size-4" />
            </a>
          )}
          <span className="inline-flex items-center gap-2 text-xs font-medium text-slate-500">
            <Icon name="shield" className="size-4 text-emerald-600" />
            Zero login required · Data stays in your browser
          </span>
        </div>

        {/* Hero highlights */}
        <dl className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {HERO_STATS.map((stat) => (
            <div
              key={stat.label}
              className="rounded-2xl border border-slate-200 bg-white/70 p-4 shadow-2xs backdrop-blur-xs transition-all hover:border-slate-300 hover:shadow-xs"
            >
              <div className="flex items-center gap-2 text-blue-600 mb-1">
                <Icon name={stat.icon} className="size-4" />
                <span className="font-display text-2xl font-black text-slate-900 leading-none">
                  {stat.value}
                </span>
              </div>
              <dt className="text-xs font-medium text-slate-500">{stat.label}</dt>
            </div>
          ))}
        </dl>
      </section>

      {/* Main interactive intake workspace */}
      <section
        id="intake-workspace"
        className="relative mx-auto grid max-w-6xl gap-6 px-4 pb-12 sm:px-6 lg:grid-cols-[minmax(0,1fr)_340px]"
      >
        {isClient ? (
          <ProfileWorkspace initial={stored} />
        ) : (
          <>
            <div className="min-w-0 space-y-6">
              <ProfileSkeleton />
            </div>
            <aside className="min-w-0 space-y-4 self-start lg:sticky lg:top-24">
              <div className={cn(CARD_CLASS, "p-6")}>
                <div className="skeleton h-5 w-36 rounded-md" />
                <div className="mt-5 space-y-3">
                  <div className="skeleton h-3.5 w-full rounded" />
                  <div className="skeleton h-3.5 w-4/5 rounded" />
                  <div className="skeleton h-3.5 w-3/5 rounded" />
                </div>
              </div>
            </aside>
          </>
        )}
      </section>

      <HowItWorks />
    </div>
  );
}

function ProfileWorkspace({ initial }: { initial: StudentProfile | null }) {
  const [draft, setDraft] = useState<StudentProfile | null>(initial);
  const [parseNote, setParseNote] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  const readiness = useMemo(
    () => (draft ? profileReadiness(draft) : []),
    [draft],
  );
  const doneCount = readiness.filter((item) => item.done).length;
  const completionPercent = readiness.length > 0 ? Math.round((doneCount / readiness.length) * 100) : 0;
  const usable = isProfileUsable(draft);

  function handleParsed(result: ParsedProfileResult) {
    setDraft(result.profile);
    saveProfile(result.profile);
    setParseNote(result.aiAvailable ? null : result.note);
    setConfirmClear(false);
  }

  function handleChange(next: StudentProfile) {
    setDraft(next);
    saveProfile(next);
  }

  function handleClear() {
    clearStoredProfile();
    setDraft(null);
    setParseNote(null);
    setConfirmClear(false);
  }

  return (
    <>
      <div className="min-w-0 space-y-6">
        {draft ? (
          <>
            {parseNote ? <AiUnavailableNotice note={parseNote} /> : null}

            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-100 px-4 py-2 text-xs text-slate-600">
              <span className="font-semibold text-slate-900">
                Active Profile: {draft.name || "Anonymous Candidate"}
              </span>
              <span>
                {draft.skills.length} {pluralize(draft.skills.length, "skill")} ·{" "}
                {draft.projects.length} {pluralize(draft.projects.length, "project")}
              </span>
            </div>

            <UploadPanel compact onParsed={handleParsed} />
            <ProfileEditor profile={draft} onChange={handleChange} />
          </>
        ) : (
          <UploadPanel onParsed={handleParsed} />
        )}
      </div>

      <aside className="min-w-0 space-y-5 self-start lg:sticky lg:top-24">
        {draft ? (
          <>
            {/* Readiness card */}
            <section className={cn(CARD_CLASS, "p-6")}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-display text-lg font-bold tracking-tight text-slate-900">
                    Profile Readiness
                  </h2>
                  <p className="text-[11px] text-slate-500">
                    {completionPercent}% completed
                  </p>
                </div>
                <span
                  className={cn(
                    "rounded-full px-2.5 py-0.5 text-xs font-bold",
                    completionPercent >= 80
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-blue-100 text-blue-800",
                  )}
                >
                  {doneCount}/{readiness.length}
                </span>
              </div>

              {/* Progress Bar */}
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-blue-600 to-emerald-500 transition-all duration-500"
                  style={{ width: `${completionPercent}%` }}
                />
              </div>

              <ul className="mt-5 space-y-3.5">
                {readiness.map((item) => (
                  <li key={item.label} className="flex items-start gap-3">
                    <span
                      className={cn(
                        "mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full text-[10px]",
                        item.done
                          ? "bg-emerald-500 text-white"
                          : "border border-slate-300 text-slate-400",
                      )}
                    >
                      {item.done ? <Icon name="check" className="size-2.5" /> : null}
                    </span>
                    <div className="min-w-0 text-xs">
                      <p
                        className={cn(
                          "font-semibold",
                          item.done ? "text-slate-900" : "text-slate-500",
                        )}
                      >
                        {item.label}
                      </p>
                      <p className="text-[11px] leading-relaxed text-slate-400">
                        {item.hint}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            {/* Ready to rank CTA */}
            <section className="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-600 via-indigo-600 to-blue-700 p-6 text-white shadow-md shadow-blue-500/15">
              <div className="flex items-center gap-2 mb-2">
                <Icon name="sparkles" className="size-4 text-emerald-300" />
                <h2 className="font-display text-lg font-bold tracking-tight">
                  Ready to Rank?
                </h2>
              </div>
              <p className="text-xs text-blue-100 leading-relaxed">
                Run our algorithm to score skills fit, degree alignment, deadline urgency, and verified safety.
              </p>
              {usable ? (
                <Link
                  href="/matches"
                  className={buttonClass("accent", "mt-5 w-full py-2.5 font-bold shadow-md")}
                >
                  See Ranked Matches
                  <Icon name="arrowRight" className="size-4" />
                </Link>
              ) : (
                <p className="mt-4 flex items-start gap-2 rounded-xl bg-white/10 p-3 text-xs leading-relaxed text-blue-100">
                  <Icon name="alert" className="mt-0.5 size-4 shrink-0 text-amber-300" />
                  Add your name or at least one technical skill to unlock matching.
                </p>
              )}
            </section>

            {confirmClear ? (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
                <p className="text-xs font-semibold text-rose-800">
                  Erase your stored profile from this browser?
                </p>
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={handleClear}
                    className={buttonClass("danger", "px-3 py-1.5 text-xs")}
                  >
                    Clear All
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmClear(false)}
                    className={buttonClass("secondary", "px-3 py-1.5 text-xs")}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmClear(true)}
                className="text-xs text-slate-400 hover:text-rose-600 hover:underline transition-colors block text-center w-full"
              >
                Reset and clear profile
              </button>
            )}
          </>
        ) : (
          <WhatYouGet />
        )}
      </aside>
    </>
  );
}

function WhatYouGet() {
  return (
    <section className={cn(CARD_CLASS, "p-6")}>
      <h2 className="font-display text-lg font-bold tracking-tight text-slate-900">
        Why Scoutly?
      </h2>
      <ul className="mt-5 space-y-4">
        {[
          {
            icon: "target" as const,
            title: "Semantic & Skill Ranking",
            body: "Combines strict skill overlaps, degree level, and embeddings similarity for meaningful ranking.",
          },
          {
            icon: "shield" as const,
            title: "Heuristic Risk Detection",
            body: "Scans listings for payment requirements, suspicious domains, and red-flag phrasing.",
          },
          {
            icon: "sparkles" as const,
            title: "Role-Specific Application Kit",
            body: "Generates actionable 3-week study roadmap, custom resume bullets, and outreach notes.",
          },
          {
            icon: "calendar" as const,
            title: "Multi-Deadline Calendar Sync",
            body: "Export up to 3 listings into an .ics calendar file with 7-day, 3-day, and 24-hour alarms.",
          },
        ].map((item) => (
          <li key={item.title} className="flex gap-3.5">
            <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 border border-blue-100">
              <Icon name={item.icon} className="size-4" />
            </span>
            <div className="min-w-0">
              <span className="block text-xs font-bold text-slate-900">
                {item.title}
              </span>
              <span className="mt-0.5 block text-xs leading-relaxed text-slate-500">
                {item.body}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function HowItWorks() {
  return (
    <section className="relative mx-auto max-w-6xl px-4 pt-10 pb-8 sm:px-6">
      <div className="flex items-center gap-4">
        <h2 className="font-display text-2xl font-bold tracking-tight text-slate-900">
          How Scoutly Works
        </h2>
        <span className="h-px flex-1 bg-slate-200" />
      </div>

      <ol className="mt-6 grid gap-4 md:grid-cols-3">
        {[
          {
            icon: "upload" as const,
            step: "01",
            title: "Drop Your Resume",
            body: "Upload a PDF or paste your plain text. Credentials are extracted client-side with 0 server recording.",
          },
          {
            icon: "filter" as const,
            step: "02",
            title: "Explore Ranked Opportunities",
            body: "See clear fit percentages, transparent risk badges, and plain-English match reasoning for each listing.",
          },
          {
            icon: "sparkles" as const,
            title: "Export Calendar & Kit",
            body: "View skill gaps, copy tailored resume bullets, and sync deadlines straight into Google or Apple Calendar.",
          },
        ].map((item) => (
          <li
            key={item.title}
            className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs transition-all hover:border-slate-300 hover:shadow-sm"
          >
            <div className="flex items-center justify-between">
              <span className="inline-flex size-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600 border border-blue-100">
                <Icon name={item.icon} className="size-5" />
              </span>
              <span className="font-display text-xl font-black text-slate-300">
                {item.step}
              </span>
            </div>
            <h3 className="mt-4 font-display text-base font-bold text-slate-900">
              {item.title}
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-slate-600">
              {item.body}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
