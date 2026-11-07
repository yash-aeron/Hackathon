"use client";

import { Icon } from "@/components/icons";
import { buttonClass } from "@/lib/ui";

interface SelectionBarProps {
  titles: string[];
  downloading: boolean;
  onDownload: () => void;
  onClear: () => void;
}

export function SelectionBar({
  titles,
  downloading,
  onDownload,
  onClear,
}: SelectionBarProps) {
  if (titles.length === 0) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 backdrop-blur-md px-4 py-3.5 shadow-2xl ring-1 ring-black/5 sm:inset-x-auto sm:bottom-6 sm:left-1/2 sm:w-[min(50rem,calc(100%-2rem))] sm:-translate-x-1/2 sm:rounded-2xl sm:border animate-fade-up">
      <div className="flex flex-wrap items-center gap-4">
        <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-xs font-black text-white shadow-xs">
          {titles.length}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-bold tracking-wider text-slate-400 uppercase">
            Ready for Calendar Sync (Max 3)
          </p>
          <p className="truncate text-xs font-semibold text-slate-800">
            {titles.join(" · ")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onClear}
            className="rounded-xl px-3 py-2 text-xs font-semibold text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={onDownload}
            disabled={downloading}
            className={buttonClass("primary", "px-4 py-2 text-xs font-bold shadow-xs")}
          >
            {downloading ? (
              <span
                className="size-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white"
                aria-hidden="true"
              />
            ) : (
              <Icon name="calendar" className="size-4" />
            )}
            {downloading ? "Building .ics…" : "Download Calendar (.ics)"}
          </button>
        </div>
      </div>
    </div>
  );
}
