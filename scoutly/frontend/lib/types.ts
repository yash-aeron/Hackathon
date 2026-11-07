/**
 * Scoutly API contract.
 *
 * These types mirror the backend contract verbatim. The backend lives in a
 * sibling repository and is developed in parallel, so nothing here may be
 * silently renamed — if a field has to change, the backend must change with it.
 */

export type ListingType = "internship" | "hackathon" | "scholarship" | "job" | "event";
export type Level = "first-year" | "second-year" | "third-year" | "final-year" | "any";
export type Mode = "remote" | "onsite" | "hybrid";
export type TrustLevel = "verified" | "caution" | "high-risk";

export interface Listing {
  id: number;
  title: string;
  organization: string;
  type: ListingType;
  description: string;
  required_skills: string[];
  level: Level;
  location: string;
  mode: Mode;
  stipend_or_prize: string | null;
  /** Calendar date, e.g. "2026-12-01". */
  deadline: string;
  apply_url: string;
  contact_email: string | null;
  source: string;
  /** ISO date, e.g. "2026-11-01". */
  posted_date: string;
  requires_payment: boolean;
}

export interface StudentProfile {
  name: string;
  education: { degree: string; college: string; year: string };
  skills: string[];
  projects: { name: string; summary: string; tech: string[] }[];
  experience: string[];
  interests: string[];
  target_types: string[];
  location_pref: string;
}

export interface TrustFlag {
  code: string;
  reason: string;
  penalty: number;
}

export interface Trust {
  score: number;
  level: TrustLevel;
  flags: TrustFlag[];
}

export interface MatchScoreBreakdown {
  /* Each component is 0..1. */
  semantic_similarity: number;
  skill_overlap: number;
  level_fit: number;
  deadline_urgency: number;
  weighted: {
    semantic_similarity: number;
    skill_overlap: number;
    level_fit: number;
    deadline_urgency: number;
  };
}

export interface Match {
  listing: Listing;
  /** 0-100, one decimal. */
  score: number;
  score_breakdown: MatchScoreBreakdown;
  why_it_fits: string;
  matched_skills: string[];
  missing_skills: string[];
  trust: Trust;
  days_left: number;
  expired: boolean;
  pinned_risky: boolean;
}

/* ------------------------------------------------------------------ */
/* Response envelopes                                                  */
/* ------------------------------------------------------------------ */

export interface HealthResponse {
  status: "ok";
  version: string;
  mock_llm: boolean;
  llm_provider: string;
  listings: number;
  embeddings_backend: string;
}

export interface ListingsResponse {
  count: number;
  listings: Listing[];
}

export interface SampleResumeResponse {
  text: string;
  profile: StudentProfile;
}

export interface ProfileParseResponse {
  profile: StudentProfile;
  raw_text: string;
  ai_available: boolean;
  note: string | null;
  source: "pdf" | "text";
}

export interface MatchMeta {
  candidates: number;
  returned: number;
  ai_available: boolean;
  note: string | null;
  embeddings_backend: string;
}

export interface MatchResponse {
  matches: Match[];
  meta: MatchMeta;
}

export interface VerifyResponse {
  trust: Trust;
  listing: Listing | null;
  ai_available: boolean;
  note: string | null;
}

export interface KitRoadmapWeek {
  week: number;
  goal: string;
  resources: string[];
}

export interface GapAnalysis {
  strengths: string[];
  gaps: string[];
  roadmap: KitRoadmapWeek[];
}

export interface KitResponse {
  listing: Listing;
  gap_analysis: GapAnalysis;
  resume_bullets: string[];
  cover_note: string;
  why_me_one_liner: string;
  ai_available: boolean;
  note: string | null;
}

/* ------------------------------------------------------------------ */
/* Request payloads                                                    */
/* ------------------------------------------------------------------ */

export interface ListingsQuery {
  types?: string[];
  mode?: string;
  limit?: number;
}

export interface ParseProfileTextInput {
  kind: "text";
  text: string;
}

export interface ParseProfileFileInput {
  kind: "file";
  file: File;
}

export type ParseProfileInput = ParseProfileTextInput | ParseProfileFileInput;

export interface MatchRequest {
  profile: StudentProfile;
  filters?: { types?: string[]; mode?: string };
  hide_risky?: boolean;
  limit?: number;
}

export type VerifyRequest = { listing_id: number } | { text: string };

export interface KitRequest {
  profile: StudentProfile;
  listing_id: number;
  regenerate?: boolean;
}

/* ------------------------------------------------------------------ */
/* Frontend-only view models                                           */
/* ------------------------------------------------------------------ */

/** A parsed profile plus the provenance needed for the inline AI notice. */
export interface ParsedProfileResult {
  profile: StudentProfile;
  aiAvailable: boolean;
  note: string | null;
  origin: "pdf" | "text" | "sample";
}

export interface StoredMatches {
  matches: Match[];
  meta: MatchMeta;
}
