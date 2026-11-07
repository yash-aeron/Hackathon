"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { Icon, type IconName } from "@/components/icons";
import { KitPanel } from "@/components/kit/kit-panel";
import { Deadline } from "@/components/ui/deadline";
import { EmptyState, ErrorState } from "@/components/ui/notices";
import { KitSkeleton } from "@/components/ui/skeleton";
import { ScoreRing } from "@/components/ui/score-ring";
import { TrustBadge } from "@/components/ui/trust-badge";
import { TypeBadge } from "@/components/ui/type-badge";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { KitResponse, Listing } from "@/lib/types";
import { CARD_CLASS, buttonClass } from "@/lib/ui";
import { useIsClient, useProfile, useStoredMatches } from "@/lib/use-stored";
import { cn, errorMessage, titleCase } from "@/lib/utils";

export function KitView({ listingId }: { listingId: number | null }) {
  const isClient = useIsClient();
  const profile = useProfile();
  const storedMatches = useStoredMatches();

  const [kit, setKit] = useState<KitResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const match =
    storedMatches?.matches.find((entry) => entry.listing.id === listingId) ??
    null;
  const listing: Listing | null = kit?.listing ?? match?.listing ?? null;

  useEffect(() => {
    if (!isClient || !profile || listingId === null) return;

    const controller = new AbortController();
    let active = true;

    (async () => {
      try {
        const data = await api.generateKit(
          {
            profile,
            listing_id: listingId,
            regenerate: attempt > 0,
          },
          controller.signal,
        );
        if (!active) return;
        setKit(data);
      } catch (caught) {
        if (!active || controller.signal.aborted) return;
        setError(
          errorMessage(
            caught,
            "Failed to draft the application kit. The listing may have expired or backend is offline.",
          ),
        );
      } finally {
        if (active) setRegenerating(false);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [attempt, isClient, listingId, profile]);

  function handleRegenerate() {
    setError(null);
    setRegenerating(true);
    setAttempt((value) => value + 1);
  }

  function handleRetry() {
    setError(null);
    setKit(null);
    setAttempt((value) => value + 1);
  }

  const loading = kit === null && error === null;

  return (
    <div className="mx-auto max-w-6xl px-4 pt-6 pb-12 sm:px-6">
      {/* Breadcrumb back link */}
      <Link
        href="/matches"
        className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 transition-colors hover:text-blue-600 mb-6"
      >
        <Icon name="arrowLeft" className="size-3.5" />
        Back to Ranked Opportunities
      </Link>

      {isClient && profile === null ? (
        <EmptyState
          icon="file"
          title="Profile Needed"
          description="Application kits are tailored specifically to your resume. Add your profile to generate custom bullets and roadmap."
          action={
            <Link href="/" className={buttonClass("primary")}>
              Upload Resume Profile
              <Icon name="arrowRight" className="size-4" />
            </Link>
          }
          className="mt-6"
        />
      ) : listingId === null ? (
        <EmptyState
          icon="alert"
          title="Invalid Listing ID"
          description="Please select an opportunity from the ranked matches list."
          action={
            <Link href="/matches" className={buttonClass("primary")}>
              Browse Matches
              <Icon name="arrowRight" className="size-4" />
            </Link>
          }
          className="mt-6"
        />
      ) : (
        <>
          {/* Executive Role Header */}
          <header className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs mb-8">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 mb-2.5">
                  {listing && <TypeBadge type={listing.type} />}
                  {match && <TrustBadge trust={match.trust} />}
                  {listing?.source && (
                    <span className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-600">
                      <Icon name="link" className="size-3 text-slate-400" />
                      {listing.source}
                    </span>
                  )}
                </div>

                <h1 className="font-display text-2xl sm:text-4xl font-extrabold tracking-tight text-slate-900 leading-tight">
                  {listing ? listing.title : loading ? "Drafting Application Kit…" : "Application Kit"}
                </h1>
                <p className="mt-1 text-sm font-semibold text-slate-500">
                  {listing ? listing.organization : "Connecting with opportunity data…"}
                </p>

                {listing && (
                  <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-600">
                    <span className="inline-flex items-center gap-1.5">
                      <Icon name="mapPin" className="size-3.5 text-slate-400" />
                      {listing.location || "Remote"}
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <Icon name="building" className="size-3.5 text-slate-400" />
                      {titleCase(listing.mode)}
                    </span>
                    {listing.stipend_or_prize && (
                      <span className="inline-flex items-center gap-1.5 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                        <Icon name="zap" className="size-3.5 text-emerald-600" />
                        {listing.stipend_or_prize}
                      </span>
                    )}
                    {match ? (
                      <Deadline
                        daysLeft={match.days_left}
                        expired={match.expired}
                        deadline={listing.deadline}
                        showDate
                      />
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500">
                        <Icon name="clock" className="size-3.5" />
                        Closes {formatDate(listing.deadline)}
                      </span>
                    )}
                  </div>
                )}
              </div>

              {match && (
                <div className="flex flex-col items-center gap-1 self-start sm:self-auto shrink-0">
                  <ScoreRing score={match.score} size={82} />
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                    Role Fit
                  </span>
                </div>
              )}
            </div>

            {match?.why_it_fits && (
              <div className="mt-5 rounded-xl border border-blue-100 bg-blue-50/50 p-4 text-xs leading-relaxed text-blue-900">
                <span className="font-bold">Algorithmic Fit Assessment: </span>
                {match.why_it_fits}
              </div>
            )}
          </header>

          {/* Main Kit Layout: Tabs on left, Snapshot on right */}
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="min-w-0">
              {error ? (
                <ErrorState
                  title="Kit Generation Failed"
                  description={error}
                  onRetry={handleRetry}
                />
              ) : loading ? (
                <KitSkeleton />
              ) : kit ? (
                <KitPanel
                  kit={kit}
                  regenerating={regenerating}
                  onRegenerate={handleRegenerate}
                />
              ) : null}
            </div>

            {/* Sidebar Snapshot & Direct Apply Action */}
            <aside className="min-w-0 self-start space-y-5 lg:sticky lg:top-24">
              {listing && (
                <section className={cn(CARD_CLASS, "p-6")}>
                  <h3 className="font-display text-sm font-bold tracking-tight text-slate-900 border-b border-slate-100 pb-3 mb-4">
                    Listing Overview
                  </h3>
                  <dl className="space-y-3.5 text-xs">
                    <SnapshotRow icon="building" label="Organization">
                      {listing.organization}
                    </SnapshotRow>
                    <SnapshotRow icon="target" label="Role Category">
                      {titleCase(listing.type)}
                    </SnapshotRow>
                    <SnapshotRow icon="mapPin" label="Workplace">
                      {listing.location || "Remote"}
                    </SnapshotRow>
                    <SnapshotRow icon="zap" label="Compensation / Prize">
                      {listing.stipend_or_prize || "Standard industry perks"}
                    </SnapshotRow>
                    <SnapshotRow icon="calendar" label="Deadline">
                      {formatDate(listing.deadline)}
                    </SnapshotRow>
                    {listing.contact_email && (
                      <SnapshotRow icon="file" label="Contact Recruiter">
                        {listing.contact_email}
                      </SnapshotRow>
                    )}
                  </dl>

                  {listing.requires_payment && (
                    <div className="mt-4 flex items-start gap-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs font-semibold text-amber-900">
                      <Icon name="alert" className="mt-0.5 size-4 shrink-0 text-amber-600" />
                      Fee Warning: This listing requests payment. Please exercise caution.
                    </div>
                  )}

                  {listing.apply_url && (
                    <a
                      href={listing.apply_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={buttonClass("primary", "mt-5 w-full py-2.5 font-bold shadow-xs")}
                    >
                      <span>Apply on Official Portal</span>
                      <Icon name="external" className="size-4" />
                    </a>
                  )}
                </section>
              )}

              <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4 text-[11px] leading-relaxed text-slate-500">
                <span className="font-semibold text-slate-700 block mb-1">
                  Applicant Advice:
                </span>
                Review all generated bullets and adapt metrics to ensure 100% honesty before submitting your application.
              </div>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}

function SnapshotRow({
  icon,
  label,
  children,
}: {
  icon: IconName;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="flex size-5 items-center justify-center rounded-md bg-slate-100 text-slate-500 mt-0.5">
        <Icon name={icon} className="size-3" />
      </span>
      <div className="min-w-0 flex-1">
        <dt className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{label}</dt>
        <dd className="mt-0.5 font-semibold text-slate-800 break-words">{children}</dd>
      </div>
    </div>
  );
}
