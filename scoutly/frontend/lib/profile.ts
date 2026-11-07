import type { StudentProfile } from "./types";

export const LISTING_TYPES = [
  "internship",
  "hackathon",
  "scholarship",
  "job",
  "event",
] as const;

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((entry): entry is string => typeof entry === "string")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

function asProjects(value: unknown): StudentProfile["projects"] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (typeof entry !== "object" || entry === null) return [];
    const project = entry as Record<string, unknown>;
    const name = asString(project.name).trim();
    const summary = asString(project.summary).trim();
    if (!name && !summary) return [];
    return [{ name, summary, tech: asStringArray(project.tech) }];
  });
}

/** Coerce whatever the API (or localStorage) returned into a complete profile. */
export function normalizeProfile(input: unknown): StudentProfile {
  const source = asRecord(input);
  const education = asRecord(source.education);
  return {
    name: asString(source.name).trim(),
    education: {
      degree: asString(education.degree).trim(),
      college: asString(education.college).trim(),
      year: asString(education.year).trim(),
    },
    skills: asStringArray(source.skills),
    projects: asProjects(source.projects),
    experience: asStringArray(source.experience),
    interests: asStringArray(source.interests),
    target_types: asStringArray(source.target_types),
    location_pref: asString(source.location_pref).trim(),
  };
}

export function createEmptyProfile(): StudentProfile {
  return {
    name: "",
    education: { degree: "", college: "", year: "" },
    skills: [],
    projects: [],
    experience: [],
    interests: [],
    target_types: [],
    location_pref: "",
  };
}

/** A profile is usable once it has a name or at least one skill. */
export function isProfileUsable(profile: StudentProfile | null): boolean {
  if (!profile) return false;
  return profile.name.trim().length > 0 || profile.skills.length > 0;
}

export interface ReadinessCheck {
  label: string;
  hint: string;
  done: boolean;
}

/** Small derived checklist shown beside the profile editor. */
export function profileReadiness(profile: StudentProfile): ReadinessCheck[] {
  return [
    {
      label: "Your name",
      hint: "Used in your cover note signature.",
      done: profile.name.trim().length > 0,
    },
    {
      label: "Education",
      hint: "Degree, college and year of study.",
      done:
        profile.education.degree.trim().length > 0 &&
        profile.education.college.trim().length > 0,
    },
    {
      label: "At least 3 skills",
      hint: "The strongest signal for skill-overlap scoring.",
      done: profile.skills.length >= 3,
    },
    {
      label: "A project to talk about",
      hint: "Powers your resume bullets and gap plan.",
      done: profile.projects.length > 0,
    },
    {
      label: "Target opportunity types",
      hint: "Narrows the search before ranking.",
      done: profile.target_types.length > 0,
    },
  ];
}

/** De-duplicate and trim a chip list, preserving order. */
export function uniqueValues(values: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of values) {
    const value = raw.trim();
    if (!value) continue;
    const key = value.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(value);
  }
  return result;
}
