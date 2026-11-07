"use client";

import Link from "next/link";
import { Icon } from "@/components/icons";
import { Deadline } from "@/components/ui/deadline";
import { ScoreRing } from "@/components/ui/score-ring";
import { TrustBadge } from "@/components/ui/trust-badge";
import { TypeBadge } from "@/components/ui/type-badge";
import type { Match } from "@/lib/types";
import { CARD_CLASS } from "@/lib/ui";
import { cn, titleCase } from "@/lib/utils";

interface MatchCardProps {
  match: Match;
  rank: number;
  selected: boolean;
  selectionDisabled: boolean;
  onToggleSelected: () => void;
}

export function MatchCard({
  match,
  rank,
  selected,
  selectionDisabled,
  onToggleSelected,
}: MatchCardProps) {
  const { listing, trust } = match;
  const risky = match.pinned_risky || trust.level === "high-risk";
  const kitHref = `/kit/${listing.id}`;
  const locationRepeatsMode =
    listing.location.trim().toLowerCase() === listing.mode.toLowerCase();

  return (
    <article
      className={cn(
        CARD_CLASS,
        "relative overflow-hidden transition-all duration-200",
        risky ? "border-rose-300 ring-1 ring-rose-200" : "border-slate-200",
        selected && "border-blue-500 ring-2 ring-blue-500/20 bg-blue-50/20",
      )}
    >
      {/* Risk alert banner */}
      {risky ? (
        <div className="flex items-center gap-2 border-b border-rose-200 bg-rose-50 px-5 py-2 text-xs font-bold text-rose-800">
          <Icon name="alert" className="size-4 shrink-0 text-rose-600" />
          <span>Risk signals detected — verify terms & source authenticity before applying.</span>
        </div>
      ) : null}

      <div className="flex flex-col gap-5 p-5 sm:p-6 sm:flex-row sm:items-start sm:gap-6">
        {/* Left column: Rank & Score Ring */}
        <div className="flex items-center justify-between sm:flex-col sm:items-center sm:justify-start gap-3 sm:w-20 shrink-0">
          <span className="flex size-7 items-center justify-center rounded-lg bg-slate-100 font-display text-xs font-black text-slate-700">
            #{rank}
          </span>
          <ScoreRing score={match.score} size={74} />
        </div>

        {/* Center column: Opportunity Details */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <TypeBadge type={listing.type} />
            {listing.source ? (
              <span className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                <Icon name="link" className="size-3 text-slate-400" />
                {listing.source}
              </span>
            ) : null}
            {listing.requires_payment ? (
              <span className="inline-flex items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-800">
                <Icon name="alert" className="size-3 text-amber-600" />
                Fee Required
              </span>
            ) : null}
          </div>

          <h3 className="mt-2.5 font-display text-xl font-bold tracking-tight text-slate-900 leading-snug">
            <Link
              href={kitHref}
              className="hover:text-blue-600 transition-colors"
            >
              {listing.title}
            </Link>
          </h3>
          <p className="mt-0.5 text-xs font-semibold text-slate-500">
            {listing.organization}
          </p>

          <p className="mt-3 text-xs leading-relaxed text-slate-600 bg-slate-50/70 rounded-xl p-3 border border-slate-100">
            <strong className="text-slate-800 font-semibold">Why this fits: </strong>
            {match.why_it_fits}
          </p>

          {/* Matched and missing skills */}
          {(match.matched_skills.length > 0 || match.missing_skills.length > 0) && (
            <div className="mt-3 flex flex-wrap gap-1.5 items-center">
              {match.matched_skills.map((skill) => (
                <span
                  key={`matched-${skill}`}
                  className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800"
                >
                  <Icon name="check" className="size-3 text-emerald-600" />
                  {skill}
                </span>
              ))}
              {match.missing_skills.map((skill) => (
                <span
                  key={`missing-${skill}`}
                  className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500"
                >
                  <span className="text-slate-400">Need:</span> {skill}
                </span>
              ))}
            </div>
          )}

          {/* Meta badges: Location, mode, stipend, deadline */}
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-600">
            <span className="inline-flex items-center gap-1.5">
              <Icon name="mapPin" className="size-3.5 text-slate-400" />
              {listing.location || "Remote / Anywhere"}
            </span>
            {!locationRepeatsMode && (
              <span className="inline-flex items-center gap-1.5">
                <Icon name="building" className="size-3.5 text-slate-400" />
                {titleCase(listing.mode)}
              </span>
            )}
            {listing.stipend_or_prize && (
              <span className="inline-flex items-center gap-1.5 font-bold text-emerald-700 bg-emerald-50/80 px-2 py-0.5 rounded-md border border-emerald-200/60">
                <Icon name="zap" className="size-3.5 text-emerald-600" />
                {listing.stipend_or_prize}
              </span>
            )}
            <Deadline
              daysLeft={match.days_left}
              expired={match.expired}
              deadline={listing.deadline}
              showDate
            />
          </div>

          {/* Bottom actions: Trust badge on left, View Kit on right */}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3.5">
            <TrustBadge trust={trust} />
            <Link
              href={kitHref}
              className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700 transition-all active:scale-[0.98]"
            >
              Open Application Kit
              <Icon name="arrowRight" className="size-3.5" />
            </Link>
          </div>
        </div>

        {/* Right column: Multi-select checkbox */}
        <div className="order-first flex justify-end sm:order-none sm:items-start">
          <label
            className={cn(
              "inline-flex cursor-pointer items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition-all select-none",
              selected
                ? "border-blue-500 bg-blue-50 text-blue-700 shadow-2xs"
                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50",
              selectionDisabled && !selected && "cursor-not-allowed opacity-40",
            )}
          >
            <input
              type="checkbox"
              checked={selected}
              disabled={selectionDisabled && !selected}
              onChange={onToggleSelected}
              className="size-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              aria-label={`Select ${listing.title} for calendar export`}
            />
            <span>Calendar</span>
          </label>
        </div>
      </div>
    </article>
  );
}
