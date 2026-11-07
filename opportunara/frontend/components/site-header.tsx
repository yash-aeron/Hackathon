"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/icons";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Profile & Intake", icon: "file" as const },
  { href: "/matches", label: "Ranked Matches", icon: "target" as const },
];

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex items-center gap-8">
          <Link
            href="/"
            className="group flex items-center gap-2.5 rounded-xl transition-transform active:scale-[0.98]"
            aria-label="Scoutly home"
          >
            <span className="inline-flex size-9 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-emerald-500 text-white shadow-xs shadow-blue-500/20 ring-1 ring-black/5">
              <Icon name="radar" className="size-5 transition-transform group-hover:rotate-45 duration-300" strokeWidth={2.2} />
            </span>
            <div className="flex flex-col">
              <span className="font-display text-xl font-bold tracking-tight text-slate-900 leading-none">
                Scoutly
              </span>
              <span className="text-[10px] font-semibold text-blue-600 tracking-wider uppercase mt-0.5">
                AI Opportunity Radar
              </span>
            </div>
          </Link>

          <nav aria-label="Primary" className="hidden sm:flex h-full items-center gap-1.5">
            {NAV_ITEMS.map((item) => {
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-[color,background-color] duration-150",
                    active
                      ? "bg-slate-100 text-slate-900 font-bold"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                  )}
                >
                  <Icon
                    name={item.icon}
                    className={cn(
                      "size-3.5",
                      active ? "text-blue-600" : "text-slate-400",
                    )}
                  />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="hidden sm:flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500">
            <Icon name="shield" className="size-3.5 text-emerald-600" />
            Zero Data Retention
          </span>
        </div>
      </div>

      {/* Mobile nav bar */}
      <div className="flex sm:hidden border-t border-slate-100 bg-white/95 px-4 py-2 justify-around">
        {NAV_ITEMS.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium",
                active
                  ? "bg-blue-50 text-blue-700 font-semibold"
                  : "text-slate-600 hover:text-slate-900",
              )}
            >
              <Icon name={item.icon} className="size-3.5" />
              {item.label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}
