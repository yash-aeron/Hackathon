"use client";

import { useEffect, useId, useState } from "react";
import { clamp, cn } from "@/lib/utils";

const RADIUS = 40;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

interface ScoreRingProps {
  score: number;
  size?: number;
  className?: string;
  label?: string;
  showText?: boolean;
}

export function ScoreRing({
  score,
  size = 76,
  className,
  label = "Match score",
  showText = true,
}: ScoreRingProps) {
  const gradientId = `ring-${useId().replace(/:/g, "")}`;
  const target = clamp(Math.round(score), 0, 100);
  const [shown, setShown] = useState(0);

  useEffect(() => {
    const frame = requestAnimationFrame(() => setShown(target));
    return () => cancelAnimationFrame(frame);
  }, [target]);

  const tone =
    target >= 75
      ? {
          from: "#10b981",
          to: "#059669",
          text: "text-emerald-700",
          bg: "bg-emerald-50",
          track: "stroke-emerald-100",
        }
      : target >= 50
        ? {
            from: "#f59e0b",
            to: "#d97706",
            text: "text-amber-700",
            bg: "bg-amber-50",
            track: "stroke-amber-100",
          }
        : {
            from: "#f43f5e",
            to: "#e11d48",
            text: "text-rose-700",
            bg: "bg-rose-50",
            track: "stroke-rose-100",
          };

  const offset = CIRCUMFERENCE - (CIRCUMFERENCE * shown) / 100;

  return (
    <div
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center rounded-full p-1",
        tone.bg,
        className,
      )}
      style={{ width: size, height: size }}
    >
      <svg
        viewBox="0 0 100 100"
        width={size - 8}
        height={size - 8}
        role="img"
        aria-label={`${label} ${target} out of 100`}
        className="-rotate-90"
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={tone.from} />
            <stop offset="100%" stopColor={tone.to} />
          </linearGradient>
        </defs>
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          className={tone.track}
          strokeWidth="8"
        />
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-1000 ease-out"
        />
      </svg>
      {showText && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span
            className={cn(
              "font-display text-lg leading-none font-extrabold tracking-tight",
              tone.text,
            )}
          >
            {target}%
          </span>
          <span className="text-[8px] font-bold text-slate-500 uppercase tracking-wider mt-0.5">
            match
          </span>
        </div>
      )}
    </div>
  );
}
