import { Icon } from "@/components/icons";

export function SiteFooter() {
  return (
    <footer className="mt-20 border-t border-slate-200 bg-white text-slate-600">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex items-center gap-3">
          <span className="inline-flex size-7 items-center justify-center rounded-lg bg-slate-900 text-white">
            <Icon name="radar" className="size-4 text-emerald-400" />
          </span>
          <span className="font-display font-bold text-slate-900">Scoutly</span>
          <span className="text-xs text-slate-400">|</span>
          <span className="text-xs text-slate-500">
            Engineered for Indian engineering students
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-6 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <Icon name="shield" className="size-3.5 text-emerald-600" />
            100% Client-Side Privacy (Zero Server Persistence)
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Icon name="checkCircle" className="size-3.5 text-blue-600" />
            Algorithmic Fit & Trust Scoring
          </span>
        </div>
      </div>
    </footer>
  );
}
