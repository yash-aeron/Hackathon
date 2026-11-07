"use client";

import { useId, useState } from "react";
import { Icon } from "@/components/icons";
import type { Trust, TrustLevel } from "@/lib/types";
import { cn } from "@/lib/utils";

const TONE: Record<
  TrustLevel,
  {
    pill: string;
    dot: string;
    icon: "shield" | "alert" | "alertCircle";
    label: string;
  }
> = {
  verified: {
    pill: "border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100/80",
    dot: "bg-emerald-500",
    icon: "shield",
    label: "Verified Safe",
  },
  caution: {
    pill: "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100/80",
    dot: "bg-amber-500",
    icon: "alert",
    label: "Caution Advised",
  },
  "high-risk": {
    pill: "border-rose-200 bg-rose-50 text-rose-800 hover:bg-rose-100/80",
    dot: "bg-rose-500",
    icon: "alertCircle",
    label: "High Risk Flagged",
  },
};

export function TrustBadge({
  trust,
  defaultOpen = false,
}: {
  trust: Trust;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();
  const tone = TONE[trust.level] ?? TONE.caution;

  return (
    <div className="relative inline-block text-left">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={panelId}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold shadow-2xs transition-[background-color,border-color] duration-150",
          tone.pill,
        )}
      >
        <Icon name={tone.icon} className="size-3.5" />
        <span>{tone.label}</span>
        <span className="font-bold opacity-75">
          ({Math.round(trust.score)}/100)
        </span>
        <Icon
          name="chevronDown"
          className={cn("size-3 transition-transform duration-200", open && "rotate-180")}
        />
      </button>

      {open && (
        <div
          id={panelId}
          className="mt-2 w-72 rounded-xl border border-slate-200 bg-white p-3.5 text-xs shadow-lg ring-1 ring-black/5 animate-fade-up z-20"
        >
          <div className="flex items-center justify-between border-b border-slate-100 pb-2 mb-2.5">
            <span className="font-semibold text-slate-800">Trust Breakdown</span>
            <span className="font-mono text-[11px] font-bold text-slate-500">
              Score: {Math.round(trust.score)}
            </span>
          </div>

          {trust.flags.length === 0 ? (
            <p className="flex items-start gap-2 leading-relaxed text-emerald-700">
              <Icon name="checkCircle" className="mt-0.5 size-4 shrink-0 text-emerald-600" />
              Verified source, legitimate contact information, and no payment requirements found.
            </p>
          ) : (
            <ul className="space-y-2">
              {trust.flags.map((flag, index) => (
                <li
                  key={`${flag.code}-${index}`}
                  className="flex items-start gap-2 leading-relaxed text-slate-700"
                >
                  <Icon
                    name="alert"
                    className="mt-0.5 size-3.5 shrink-0 text-amber-600"
                  />
                  <span>
                    <span className="font-medium text-slate-900">{flag.reason}</span>{" "}
                    <span className="font-mono text-[10px] font-bold text-rose-600">
                      (-{flag.penalty} pts)
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
