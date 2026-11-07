import { Icon } from "@/components/icons";
import { deadlineInfo, formatDate, type DeadlineTone } from "@/lib/format";
import { cn } from "@/lib/utils";

const TONE_CONFIG: Record<
  DeadlineTone,
  { text: string; bg: string; iconColor: string }
> = {
  expired: {
    text: "text-rose-700 font-semibold",
    bg: "bg-rose-50 border-rose-200",
    iconColor: "text-rose-600",
  },
  today: {
    text: "text-amber-800 font-bold",
    bg: "bg-amber-50 border-amber-200",
    iconColor: "text-amber-600",
  },
  urgent: {
    text: "text-rose-700 font-semibold",
    bg: "bg-rose-50 border-rose-200",
    iconColor: "text-rose-600",
  },
  warn: {
    text: "text-amber-700 font-medium",
    bg: "bg-amber-50 border-amber-200",
    iconColor: "text-amber-600",
  },
  calm: {
    text: "text-slate-600 font-medium",
    bg: "bg-slate-50 border-slate-200",
    iconColor: "text-slate-500",
  },
};

export function Deadline({
  daysLeft,
  expired,
  deadline,
  showDate = false,
  className,
}: {
  daysLeft: number;
  expired: boolean;
  deadline: string;
  showDate?: boolean;
  className?: string;
}) {
  const info = deadlineInfo(daysLeft, expired);
  const tone = TONE_CONFIG[info.tone] ?? TONE_CONFIG.calm;

  return (
    <span
      className={cn(
        "inline-flex flex-wrap items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs shadow-2xs",
        tone.bg,
        tone.text,
        className,
      )}
    >
      <Icon name="clock" className={cn("size-3", tone.iconColor)} />
      <span>{info.text}</span>
      {showDate ? (
        <span className="font-normal opacity-75">
          · {formatDate(deadline)}
        </span>
      ) : null}
    </span>
  );
}
