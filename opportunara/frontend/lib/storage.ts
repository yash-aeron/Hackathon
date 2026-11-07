import { normalizeProfile } from "./profile";
import type { Match, MatchMeta, StudentProfile, StoredMatches } from "./types";

export const PROFILE_STORAGE_KEY = "scoutly.profile.v1";
export const MATCHES_STORAGE_KEY = "scoutly.matches.v1";

/** Fired after we mutate localStorage so same-tab subscribers re-render. */
export const STORAGE_EVENT = "scoutly:storage";

function safeRead(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    // Safari private mode / storage disabled — the app still works, minus
    // persistence between screens.
    return null;
  }
}

function safeWrite(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
    window.dispatchEvent(new Event(STORAGE_EVENT));
  } catch {
    // Quota exceeded or storage blocked. Nothing useful to surface here.
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

const FALLBACK_META: MatchMeta = {
  candidates: 0,
  returned: 0,
  ai_available: true,
  note: null,
  embeddings_backend: "unknown",
};

export function parseStoredMatches(raw: string | null): StoredMatches | null {
  if (!raw) return null;
  try {
    const data: unknown = JSON.parse(raw);
    if (!isRecord(data) || !Array.isArray(data.matches)) return null;
    const matches = data.matches.filter((entry): entry is Match => {
      if (!isRecord(entry)) return false;
      const listing = entry.listing;
      return isRecord(listing) && typeof listing.id === "number";
    });
    return {
      matches,
      meta: isRecord(data.meta)
        ? (data.meta as unknown as MatchMeta)
        : { ...FALLBACK_META, returned: matches.length },
    };
  } catch {
    return null;
  }
}

export function parseStoredProfile(raw: string | null): StudentProfile | null {
  if (!raw) return null;
  try {
    const data: unknown = JSON.parse(raw);
    if (!isRecord(data)) return null;
    const profile = normalizeProfile(data);
    return profile;
  } catch {
    return null;
  }
}

export function readStoredProfile(): StudentProfile | null {
  return parseStoredProfile(safeRead(PROFILE_STORAGE_KEY));
}

export function readStoredMatches(): StoredMatches | null {
  return parseStoredMatches(safeRead(MATCHES_STORAGE_KEY));
}

export function saveProfile(profile: StudentProfile): void {
  safeWrite(PROFILE_STORAGE_KEY, JSON.stringify(profile));
}

export function saveMatches(matches: Match[], meta: MatchMeta): void {
  const payload: StoredMatches = { matches, meta };
  safeWrite(MATCHES_STORAGE_KEY, JSON.stringify(payload));
}

export function clearStoredProfile(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(PROFILE_STORAGE_KEY);
    window.localStorage.removeItem(MATCHES_STORAGE_KEY);
    window.dispatchEvent(new Event(STORAGE_EVENT));
  } catch {
    // Ignore — nothing to clear if storage is blocked.
  }
}
