"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { FilterBar } from "@/components/matches/filter-bar";
import { MatchCard } from "@/components/matches/match-card";
import { SelectionBar } from "@/components/matches/selection-bar";
import { VerifyModal } from "@/components/matches/verify-modal";
import { LoadingPanel } from "@/components/ui/loading-messages";
import {
  AiUnavailableNotice,
  EmptyState,
  ErrorState,
} from "@/components/ui/notices";
import { MatchListSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { saveMatches } from "@/lib/storage";
import type { ListingType, Match, MatchResponse, Mode } from "@/lib/types";
import { buttonClass } from "@/lib/ui";
import { useIsClient, useProfile } from "@/lib/use-stored";
import { cn, downloadBlob, errorMessage, pluralize } from "@/lib/utils";

const MAX_SELECTION = 3;

const SCORING_MESSAGES = [
  "Evaluating 60+ verified opportunities…",
  "Computing skills overlap and degree relevance…",
  "Checking source trust and deadline urgency…",
];

type MatchesView =
  | { key: string; status: "ok"; data: MatchResponse }
  | { key: string; status: "error"; message: string };

function orderMatches(matches: Match[]): Match[] {
  return [...matches].sort((a, b) => {
    const byRisk = Number(a.pinned_risky) - Number(b.pinned_risky);
    if (byRisk !== 0) return byRisk;
    return b.score - a.score;
  });
}

export default function MatchesPage() {
  const isClient = useIsClient();
  const profile = useProfile();
  const toast = useToast();

  const [types, setTypes] = useState<ListingType[]>([]);
  const [mode, setMode] = useState<Mode | "any">("any");
  const [hideRisky, setHideRisky] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [downloading, setDownloading] = useState(false);
  const [view, setView] = useState<MatchesView | null>(null);

  const queryKey = JSON.stringify([types, mode, hideRisky, attempt]);

  useEffect(() => {
    if (!profile) return;
    const controller = new AbortController();
    let active = true;

    (async () => {
      try {
        const data = await api.match(
          {
            profile,
            filters: {
              ...(types.length > 0 ? { types } : {}),
              ...(mode !== "any" ? { mode } : {}),
            },
            hide_risky: hideRisky,
            limit: 60,
          },
          controller.signal,
        );
        if (!active) return;
        saveMatches(data.matches, data.meta);
        setView({ key: queryKey, status: "ok", data });
      } catch (caught) {
        if (!active || controller.signal.aborted) return;
        const message = errorMessage(
          caught,
          "Failed to calculate match rankings.",
        );
        setView({ key: queryKey, status: "error", message });
        toast({
          kind: "error",
          title: "Ranking Error",
          description: message,
        });
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [profile, queryKey, types, mode, hideRisky, toast]);

  const activeView = view && view.key === queryKey ? view : null;
  const data = activeView?.status === "ok" ? activeView.data : null;
  const ordered = data ? orderMatches(data.matches) : [];
  const riskyCount = ordered.filter(
    (match) => match.pinned_risky || match.trust.level === "high-risk",
  ).length;

  const selectedMatches = ordered.filter((match) =>
    selected.includes(match.listing.id),
  );
  const selectedIds = selectedMatches.map((match) => match.listing.id);
  const selectedTitles = selectedMatches.map((match) => match.listing.title);

  const loading = isClient && profile !== null && activeView === null;

  function toggleType(type: ListingType) {
    setTypes((current) =>
      current.includes(type)
        ? current.filter((value) => value !== type)
        : [...current, type],
    );
  }

  function clearFilters() {
    setTypes([]);
    setMode("any");
    setHideRisky(false);
  }

  function toggleSelected(id: number) {
    if (selected.includes(id)) {
      setSelected(selected.filter((value) => value !== id));
      return;
    }
    if (selected.length >= MAX_SELECTION) {
      toast({
        kind: "info",
        title: `Limit: ${MAX_SELECTION} listings`,
        description: "Deselect one to add another for calendar export.",
      });
      return;
    }
    setSelected([...selected, id]);
  }

  async function handleDownload() {
    if (selectedIds.length === 0) return;
    setDownloading(true);
    try {
      const blob = await api.calendarIcs(selectedIds);
      downloadBlob(blob, "scoutly-deadlines.ics");
      toast({
        kind: "success",
        title: "Calendar file ready",
        description: `${selectedIds.length} ${pluralize(
          selectedIds.length,
          "deadline",
        )} exported to scoutly-deadlines.ics.`,
      });
    } catch (caught) {
      toast({
        kind: "error",
        title: "Calendar download failed",
        description: errorMessage(
          caught,
          "Failed to build the calendar file. Please try again.",
        ),
      });
    } finally {
      setDownloading(false);
    }
  }

  const contextLine = profile
    ? [
        profile.education.degree || "Engineering Student",
        `${profile.skills.length} ${pluralize(profile.skills.length, "skill")}`,
        profile.target_types.length > 0
          ? profile.target_types.join(", ")
          : "All opportunity types",
      ].join(" · ")
    : "Upload your resume once to unlock custom algorithmic matching.";

  return (
    <div className={cn("mx-auto max-w-6xl px-4 pt-8 sm:px-6", selected.length > 0 && "pb-36")}>
      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-0.5 text-xs font-bold text-blue-700 mb-2">
            <Icon name="target" className="size-3.5" />
            Ranked Matching Engine
          </div>
          <h1 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900">
            {profile ? (
              <>
                Matches for <span className="text-blue-600">{profile.name || "You"}</span>
              </>
            ) : (
              "Ranked Opportunities"
            )}
          </h1>
          <p className="mt-1.5 text-xs sm:text-sm text-slate-500 font-medium">
            {contextLine}
          </p>
        </div>
        <Link href="/" className={buttonClass("secondary", "self-start sm:self-auto")}>
          <Icon name="file" className="size-4" />
          Edit Resume Profile
        </Link>
      </header>

      {/* Filter toolbar */}
      <div className="mt-6">
        <FilterBar
          types={types}
          onToggleType={toggleType}
          onClearTypes={() => setTypes([])}
          mode={mode}
          onModeChange={setMode}
          hideRisky={hideRisky}
          onHideRiskyChange={setHideRisky}
          onCheckListing={() => setVerifyOpen(true)}
        />
      </div>

      {/* Main listing feed */}
      <div className="mt-6">
        {!isClient ? (
          <div className="space-y-4">
            <LoadingPanel messages={SCORING_MESSAGES} />
            <MatchListSkeleton />
          </div>
        ) : profile === null ? (
          <EmptyState
            icon="file"
            title="Profile not found"
            description="Scoutly requires a resume profile to rank opportunities by skill overlap and academic level."
            action={
              <Link href="/" className={buttonClass("primary")}>
                Upload Resume
                <Icon name="arrowRight" className="size-4" />
              </Link>
            }
          />
        ) : loading ? (
          <div className="space-y-4">
            <LoadingPanel
              messages={SCORING_MESSAGES}
              hint="Evaluating semantic embeddings and trust flags against your profile."
            />
            <MatchListSkeleton />
          </div>
        ) : activeView?.status === "error" ? (
          <ErrorState
            title="Unable to rank matches"
            description={activeView.message}
            onRetry={() => setAttempt((value) => value + 1)}
          />
        ) : data ? (
          <>
            {data.meta.ai_available === false && (
              <AiUnavailableNotice note={data.meta.note} className="mb-4" />
            )}

            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
              <span>
                Showing {data.meta.returned} of {data.meta.candidates} candidate listings ·{" "}
                Backend: {data.meta.embeddings_backend}
              </span>
              <span>
                Select up to {MAX_SELECTION} opportunities to export a synchronized .ics calendar.
              </span>
            </div>

            {ordered.length === 0 ? (
              <EmptyState
                icon="filter"
                title="No opportunities match the selected filters"
                description="Try clearing your category or location filters to see more listings."
                action={
                  <button
                    type="button"
                    onClick={clearFilters}
                    className={buttonClass("secondary")}
                  >
                    <Icon name="refresh" className="size-4" />
                    Reset Filters
                  </button>
                }
              />
            ) : (
              <ol className="space-y-4">
                {ordered.map((match, index) => {
                  const previous = ordered[index - 1];
                  const showRiskDivider =
                    match.pinned_risky &&
                    (!previous || !previous.pinned_risky);
                  return (
                    <li key={match.listing.id} className="space-y-4">
                      {showRiskDivider && (
                        <div className="flex items-center gap-3 pt-4 pb-1">
                          <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-bold text-rose-800 shadow-2xs">
                            <Icon name="alert" className="size-3.5 text-rose-600" />
                            {riskyCount} {pluralize(riskyCount, "listing")} with Risk Signals
                          </span>
                          <span className="h-px flex-1 bg-rose-200" />
                          <span className="text-xs text-slate-400">
                            Deprioritized below verified safe matches
                          </span>
                        </div>
                      )}
                      <MatchCard
                        match={match}
                        rank={index + 1}
                        selected={selected.includes(match.listing.id)}
                        selectionDisabled={selected.length >= MAX_SELECTION}
                        onToggleSelected={() =>
                          toggleSelected(match.listing.id)
                        }
                      />
                    </li>
                  );
                })}
              </ol>
            )}
          </>
        ) : null}
      </div>

      <SelectionBar
        titles={selectedTitles}
        downloading={downloading}
        onDownload={() => void handleDownload()}
        onClear={() => setSelected([])}
      />

      {verifyOpen && <VerifyModal onClose={() => setVerifyOpen(false)} />}
    </div>
  );
}
