"use client";

import { useState, type FormEvent } from "react";
import { Icon } from "@/components/icons";
import { Modal } from "@/components/ui/modal";
import { AiUnavailableNotice } from "@/components/ui/notices";
import { ScoreRing } from "@/components/ui/score-ring";
import { TrustBadge } from "@/components/ui/trust-badge";
import { TypeBadge } from "@/components/ui/type-badge";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { VerifyResponse } from "@/lib/types";
import { buttonClass, INPUT_CLASS, LABEL_CLASS } from "@/lib/ui";
import { cn, errorMessage, titleCase } from "@/lib/utils";

const MIN_LENGTH = 25;

export function VerifyModal({ onClose }: { onClose: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  const canSubmit = text.trim().length >= MIN_LENGTH && !busy;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = text.trim();
    if (trimmed.length < MIN_LENGTH) {
      toast({
        kind: "error",
        title: "More text required",
        description: `Paste at least ${MIN_LENGTH} characters of the listing.`,
      });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await api.verify({ text: trimmed });
      setResult(response);
    } catch (caught) {
      const message = errorMessage(caught, "Couldn't verify the listing.");
      setError(message);
      toast({ kind: "error", title: "Verification failed", description: message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Verify External Listing"
      description="Found an internship on Telegram, WhatsApp, or a job board? Paste the full post below to analyze source legitimacy, fee requests, and red flags."
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="verify-text" className={LABEL_CLASS}>
            Listing Description & Contact Text
          </label>
          <textarea
            id="verify-text"
            rows={6}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Paste title, organization, description, stipend details, and contact email/link..."
            aria-describedby="verify-text-hint"
            className={cn(INPUT_CLASS, "resize-y text-xs font-sans leading-relaxed")}
          />
          <div className="mt-1.5 flex items-center justify-between text-xs text-slate-500">
            <span>Minimum {MIN_LENGTH} characters required</span>
            <span className={cn(canSubmit ? "text-emerald-600 font-semibold" : "text-slate-400")}>
              {text.trim().length} chars
            </span>
          </div>
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          className={buttonClass("primary", "w-full py-2.5")}
        >
          {busy ? (
            <span
              className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
              aria-hidden="true"
            />
          ) : (
            <Icon name="shield" className="size-4" />
          )}
          {busy ? "Analyzing Risk Signals…" : "Scan & Verify Listing"}
        </button>

        {error && (
          <p role="alert" className="text-xs font-semibold text-rose-600">
            {error}
          </p>
        )}
      </form>

      {result && (
        <div
          role="status"
          aria-live="polite"
          className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5 shadow-xs animate-fade-up"
        >
          <div className="flex items-start gap-4">
            <ScoreRing score={result.trust.score} size={70} label="Trust score" />
            <div className="min-w-0 flex-1">
              <h4 className="font-display text-base font-bold text-slate-900">
                Safety Rating: {Math.round(result.trust.score)}/100
              </h4>
              <p className="mt-0.5 text-xs text-slate-600 leading-relaxed">
                {result.trust.flags.length === 0
                  ? `${titleCase(result.trust.level)} — No obvious risk signals detected in the submitted text.`
                  : `${titleCase(result.trust.level)} — Identified ${result.trust.flags.length} potential risk signal(s).`}
              </p>
              <div className="mt-2.5">
                <TrustBadge trust={result.trust} defaultOpen />
              </div>
            </div>
          </div>

          {result.listing ? (
            <div className="mt-4 border-t border-slate-200 pt-3.5">
              <div className="flex items-center gap-2 mb-1">
                <TypeBadge type={result.listing.type} />
                <span className="text-xs text-slate-500 font-medium">
                  Matches Verified Record #{result.listing.id}
                </span>
              </div>
              <p className="font-display text-sm font-bold text-slate-900">
                {result.listing.title}
              </p>
              <p className="text-xs text-slate-600">
                {result.listing.organization}
              </p>
            </div>
          ) : (
            <p className="mt-4 border-t border-slate-200 pt-3 text-xs text-slate-500">
              Scanned independently against heuristic trust guidelines.
            </p>
          )}

          {result.ai_available === false && (
            <AiUnavailableNotice note={result.note} className="mt-3.5" />
          )}
        </div>
      )}
    </Modal>
  );
}
