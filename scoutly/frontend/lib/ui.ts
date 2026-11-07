import { cn } from "./utils";

export type ButtonVariant =
  | "primary"
  | "accent"
  | "secondary"
  | "outline"
  | "ghost"
  | "danger";

const BUTTON_BASE =
  "inline-flex select-none items-center justify-center gap-2 rounded-xl text-sm font-semibold transition-[color,background-color,border-color,transform,box-shadow] duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-blue-600 text-white shadow-sm hover:bg-blue-700 active:bg-blue-800",
  accent:
    "bg-emerald-600 text-white shadow-sm hover:bg-emerald-700 active:bg-emerald-800",
  secondary:
    "border border-slate-200 bg-white text-slate-800 shadow-xs hover:border-slate-300 hover:bg-slate-50 active:bg-slate-100",
  outline:
    "border border-slate-300 bg-transparent text-slate-700 hover:bg-slate-100 hover:text-slate-900",
  ghost:
    "bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900 active:bg-slate-200",
  danger:
    "border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 hover:border-rose-300 active:bg-rose-200",
};

export function buttonClass(
  variant: ButtonVariant = "primary",
  extra?: string,
): string {
  return cn(BUTTON_BASE, BUTTON_VARIANTS[variant], extra);
}

export const CARD_CLASS =
  "rounded-2xl border border-slate-200/90 bg-white shadow-[0_1px_3px_0_rgba(15,23,42,0.05),0_1px_2px_-1px_rgba(15,23,42,0.05)] transition-shadow hover:shadow-[0_4px_12px_-2px_rgba(15,23,42,0.08)]";

export const LABEL_CLASS =
  "mb-1.5 block text-xs font-semibold tracking-wide text-slate-700 uppercase";

export const INPUT_CLASS =
  "w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 shadow-2xs transition-[border-color,box-shadow] hover:border-slate-300 focus:border-blue-600 focus:ring-3 focus:ring-blue-500/15 focus:outline-none";

export const CHIP_CLASS =
  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors";
