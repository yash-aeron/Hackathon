"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface RotatingMessageProps {
  messages: string[];
  intervalMs?: number;
  className?: string;
}

export function RotatingMessage({
  messages,
  intervalMs = 1700,
  className,
}: RotatingMessageProps) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (messages.length <= 1) return;
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % messages.length);
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [messages.length, intervalMs]);

  return (
    <p
      aria-live="polite"
      className={cn("flex items-center gap-2.5 text-sm font-medium text-slate-800", className)}
    >
      <span
        className="animate-pulse-dot inline-block size-2.5 rounded-full bg-blue-600 shadow-xs shadow-blue-500/50"
        aria-hidden="true"
      />
      {messages[index] ?? messages[0]}
    </p>
  );
}

export function LoadingPanel({
  messages,
  hint,
  intervalMs,
}: {
  messages: string[];
  hint?: string;
  intervalMs?: number;
}) {
  return (
    <div
      role="status"
      className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs"
    >
      <RotatingMessage
        messages={messages}
        intervalMs={intervalMs}
        className="text-base font-semibold text-slate-900"
      />
      {hint ? (
        <p className="mt-2 text-xs leading-relaxed text-slate-500 pl-5">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
