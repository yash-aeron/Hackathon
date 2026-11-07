"use client";

import {
  useMemo,
  useSyncExternalStore,
} from "react";
import { parseStoredMatches, parseStoredProfile, STORAGE_EVENT } from "./storage";
import type { StudentProfile, StoredMatches } from "./types";

const PROFILE_KEY = "scoutly.profile.v1";
const MATCHES_KEY = "scoutly.matches.v1";

function subscribe(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(STORAGE_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(STORAGE_EVENT, onStoreChange);
  };
}

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/**
 * Raw localStorage snapshot. Returns a string (a value type) so
 * `useSyncExternalStore` can compare snapshots cheaply and never loop.
 */
export function useStoredRaw(key: string): string | null {
  return useSyncExternalStore(
    subscribe,
    () => read(key),
    () => null,
  );
}

const noopSubscribe = () => () => {};

/**
 * `false` during server rendering and the hydration pass, `true` afterwards.
 * Lets pages render a skeleton instead of flashing the "no profile" empty state
 * before localStorage is readable.
 */
export function useIsClient(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

export function useProfile(): StudentProfile | null {
  const raw = useStoredRaw(PROFILE_KEY);
  return useMemo(() => parseStoredProfile(raw), [raw]);
}

export function useStoredMatches(): StoredMatches | null {
  const raw = useStoredRaw(MATCHES_KEY);
  return useMemo(() => parseStoredMatches(raw), [raw]);
}
