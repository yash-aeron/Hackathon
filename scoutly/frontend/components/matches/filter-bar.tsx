"use client";

import { Icon } from "@/components/icons";
import type { ListingType, Mode } from "@/lib/types";
import { cn, titleCase } from "@/lib/utils";

const TYPES: ListingType[] = [
  "internship",
  "hackathon",
  "scholarship",
  "job",
  "event",
];

const MODES: Array<Mode | "any"> = ["any", "remote", "onsite", "hybrid"];

interface FilterBarProps {
  types: ListingType[];
  onToggleType: (type: ListingType) => void;
  onClearTypes: () => void;
  mode: Mode | "any";
  onModeChange: (mode: Mode | "any") => void;
  hideRisky: boolean;
  onHideRiskyChange: (value: boolean) => void;
  onCheckListing: () => void;
}

export function FilterBar({
  types,
  onToggleType,
  onClearTypes,
  mode,
  onModeChange,
  hideRisky,
  onHideRiskyChange,
  onCheckListing,
}: FilterBarProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-xs">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        {/* Opportunity Type Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1.5 text-xs font-bold text-slate-500 uppercase tracking-wider">
            Category
          </span>
          <button
            type="button"
            aria-pressed={types.length === 0}
            onClick={onClearTypes}
            className={cn(
              "rounded-xl border px-3 py-1.5 text-xs font-semibold shadow-2xs transition-all active:scale-[0.98]",
              types.length === 0
                ? "border-blue-600 bg-blue-600 text-white"
                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50",
            )}
          >
            All Types
          </button>
          {TYPES.map((type) => {
            const active = types.includes(type);
            return (
              <button
                key={type}
                type="button"
                aria-pressed={active}
                onClick={() => onToggleType(type)}
                className={cn(
                  "rounded-xl border px-3 py-1.5 text-xs font-semibold shadow-2xs transition-all active:scale-[0.98]",
                  active
                    ? "border-blue-600 bg-blue-600 text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50",
                )}
              >
                {titleCase(type)}
              </button>
            );
          })}
        </div>

        {/* Mode Selector, Risk Filter & Trust Tool */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Mode Dropdown */}
          <div className="flex items-center gap-2">
            <label
              htmlFor="match-mode"
              className="text-xs font-bold text-slate-500 uppercase tracking-wider"
            >
              Mode
            </label>
            <select
              id="match-mode"
              value={mode}
              onChange={(event) =>
                onModeChange(event.target.value as Mode | "any")
              }
              className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 shadow-2xs transition-colors hover:border-slate-300 focus:border-blue-600 focus:outline-none"
            >
              {MODES.map((value) => (
                <option key={value} value={value}>
                  {value === "any" ? "All Locations" : titleCase(value)}
                </option>
              ))}
            </select>
          </div>

          {/* Hide Risky Toggle */}
          <label className="flex items-center gap-2 cursor-pointer select-none rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors">
            <input
              type="checkbox"
              checked={hideRisky}
              onChange={(event) => onHideRiskyChange(event.target.checked)}
              className="size-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <span>Filter out risky</span>
          </label>

          {/* Verify Listing Trigger */}
          <button
            type="button"
            onClick={onCheckListing}
            className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-1.5 text-xs font-bold text-emerald-800 shadow-2xs hover:bg-emerald-100 transition-colors active:scale-[0.98]"
          >
            <Icon name="shield" className="size-3.5 text-emerald-600" />
            <span>Check External Listing</span>
          </button>
        </div>
      </div>
    </div>
  );
}
