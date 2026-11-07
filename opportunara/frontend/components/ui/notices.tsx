import type { ReactNode } from "react";
import { Icon, type IconName } from "@/components/icons";
import { buttonClass } from "@/lib/ui";
import { cn } from "@/lib/utils";

/**
 * Inline, always-visible notice used whenever the backend reports
 * `ai_available: false`. The exact wording is deliberate and must stay.
 */
export function AiUnavailableNotice({
  note,
  className,
}: {
  note?: string | null;
  className?: string;
}) {
  return (
    <div
      role="status"
      className={cn(
        "flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 shadow-xs",
        className,
      )}
    >
      <Icon name="sparkles" className="mt-0.5 size-4 shrink-0 text-amber-600" />
      <div className="text-xs leading-relaxed">
        <p className="font-bold text-amber-900">
          AI unavailable — showing basic results
        </p>
        <p className="mt-1 text-amber-800">
          {note ??
            "Ranking and copy come from the rule-based fallback. Still usable — just less nuanced."}
        </p>
      </div>
    </div>
  );
}

interface EmptyStateProps {
  icon?: IconName;
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
  iconClassName?: string;
}

export function EmptyState({
  icon = "target",
  title,
  description,
  action,
  className,
  iconClassName = "text-blue-600 bg-blue-50 border-blue-200",
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/70 px-6 py-14 text-center shadow-xs",
        className,
      )}
    >
      <span
        className={cn(
          "mb-4 inline-flex size-14 items-center justify-center rounded-2xl border shadow-xs",
          iconClassName,
        )}
      >
        <Icon name={icon} className="size-6" />
      </span>
      <h3 className="font-display text-lg font-bold text-slate-900">
        {title}
      </h3>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-slate-600">
        {description}
      </p>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title,
  description,
  onRetry,
  retryLabel = "Try again",
}: {
  title: string;
  description: string;
  onRetry: () => void;
  retryLabel?: string;
}) {
  return (
    <EmptyState
      icon="alert"
      iconClassName="text-rose-600 bg-rose-50 border-rose-200"
      title={title}
      description={description}
      action={
        <button
          type="button"
          onClick={onRetry}
          className={buttonClass("secondary")}
        >
          <Icon name="refresh" className="size-4" />
          {retryLabel}
        </button>
      }
    />
  );
}
