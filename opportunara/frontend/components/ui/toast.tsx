"use client";

import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Icon } from "@/components/icons";
import { cn } from "@/lib/utils";

export type ToastKind = "error" | "success" | "info";

export interface ToastInput {
  kind: ToastKind;
  title: string;
  description?: string;
  durationMs?: number;
}

interface ToastItem extends ToastInput {
  id: number;
}

type PushToast = (toast: ToastInput) => void;

const ToastContext = createContext<PushToast | null>(null);

const TONE: Record<
  ToastKind,
  { panel: string; bar: string; icon: string; iconName: "alert" | "check" | "info" }
> = {
  error: {
    panel: "border-rose-200 bg-white text-slate-900 shadow-xl",
    bar: "bg-rose-500",
    icon: "text-rose-600",
    iconName: "alert",
  },
  success: {
    panel: "border-emerald-200 bg-white text-slate-900 shadow-xl",
    bar: "bg-emerald-500",
    icon: "text-emerald-600",
    iconName: "check",
  },
  info: {
    panel: "border-blue-200 bg-white text-slate-900 shadow-xl",
    bar: "bg-blue-600",
    icon: "text-blue-600",
    iconName: "info",
  },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback((input: ToastInput) => {
    const id = nextId.current;
    nextId.current += 1;
    setToasts((current) => [...current.slice(-3), { ...input, id }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, input.durationMs ?? 6000);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-4 top-4 z-[100] flex flex-col items-center gap-2 sm:inset-x-auto sm:right-6 sm:top-6 sm:w-96 sm:items-end"
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map((toast) => {
          const tone = TONE[toast.kind];
          return (
            <div
              key={toast.id}
              role={toast.kind === "error" ? "alert" : "status"}
              className={cn(
                "pointer-events-auto relative w-full animate-fade-up overflow-hidden rounded-2xl border p-4 pl-4.5 ring-1 ring-black/5 transition-all",
                tone.panel,
              )}
            >
              <span
                aria-hidden="true"
                className={cn("absolute inset-y-0 left-0 w-1.5", tone.bar)}
              />
              <div className="flex items-start gap-3">
                <span className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-slate-50">
                  <Icon
                    name={tone.iconName}
                    className={cn("size-4", tone.icon)}
                  />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-bold text-slate-900">{toast.title}</p>
                  {toast.description ? (
                    <p className="mt-1 text-xs leading-relaxed text-slate-600">
                      {toast.description}
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  aria-label="Dismiss notification"
                  onClick={() => dismiss(toast.id)}
                  className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
                >
                  <Icon name="x" className="size-4" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): PushToast {
  const push = useContext(ToastContext);
  if (!push) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return push;
}
