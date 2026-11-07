import { Icon, type IconName } from "@/components/icons";
import type { ListingType } from "@/lib/types";
import { cn, titleCase } from "@/lib/utils";

const TYPE_CONFIG: Record<
  ListingType,
  { style: string; icon: IconName }
> = {
  internship: {
    style: "border-blue-200 bg-blue-50 text-blue-700",
    icon: "building",
  },
  hackathon: {
    style: "border-purple-200 bg-purple-50 text-purple-700",
    icon: "zap",
  },
  scholarship: {
    style: "border-emerald-200 bg-emerald-50 text-emerald-700",
    icon: "cap",
  },
  job: {
    style: "border-indigo-200 bg-indigo-50 text-indigo-700",
    icon: "target",
  },
  event: {
    style: "border-amber-200 bg-amber-50 text-amber-700",
    icon: "calendar",
  },
};

export function TypeBadge({
  type,
  className,
}: {
  type: ListingType;
  className?: string;
}) {
  const config = TYPE_CONFIG[type] ?? {
    style: "border-slate-200 bg-slate-50 text-slate-700",
    icon: "sparkles",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold shadow-2xs",
        config.style,
        className,
      )}
    >
      <Icon name={config.icon} className="size-3" />
      {titleCase(type)}
    </span>
  );
}
