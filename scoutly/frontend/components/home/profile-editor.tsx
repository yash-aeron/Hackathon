"use client";

import { useState, type ReactNode } from "react";
import { Icon, type IconName } from "@/components/icons";
import { LISTING_TYPES, uniqueValues } from "@/lib/profile";
import type { StudentProfile } from "@/lib/types";
import {
  CARD_CLASS,
  CHIP_CLASS,
  INPUT_CLASS,
  LABEL_CLASS,
  buttonClass,
} from "@/lib/ui";
import { cn, titleCase } from "@/lib/utils";

const YEAR_OPTIONS = [
  "1st year",
  "2nd year",
  "3rd year",
  "4th year",
  "Final year",
  "Graduated",
];

interface ProfileEditorProps {
  profile: StudentProfile;
  onChange: (next: StudentProfile) => void;
}

export function ProfileEditor({ profile, onChange }: ProfileEditorProps) {
  const yearOptions =
    profile.education.year && !YEAR_OPTIONS.includes(profile.education.year)
      ? [...YEAR_OPTIONS, profile.education.year]
      : YEAR_OPTIONS;

  function update(patch: Partial<StudentProfile>) {
    onChange({ ...profile, ...patch });
  }

  function updateEducation(patch: Partial<StudentProfile["education"]>) {
    onChange({
      ...profile,
      education: { ...profile.education, ...patch },
    });
  }

  function updateProject(
    index: number,
    patch: Partial<StudentProfile["projects"][number]>,
  ) {
    onChange({
      ...profile,
      projects: profile.projects.map((project, projectIndex) =>
        projectIndex === index ? { ...project, ...patch } : project,
      ),
    });
  }

  function addProject() {
    onChange({
      ...profile,
      projects: [
        ...profile.projects,
        { name: "", summary: "", tech: [] },
      ],
    });
  }

  function removeProject(index: number) {
    onChange({
      ...profile,
      projects: profile.projects.filter((_, projectIndex) => projectIndex !== index),
    });
  }

  function toggleTargetType(type: string) {
    const selected = profile.target_types.includes(type);
    update({
      target_types: selected
        ? profile.target_types.filter((value) => value !== type)
        : [...profile.target_types, type],
    });
  }

  return (
    <div className={cn(CARD_CLASS, "p-6 sm:p-8")}>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-5 mb-6">
        <div>
          <h2 className="font-display text-xl font-bold tracking-tight text-slate-900">
            Candidate Profile
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Changes auto-save locally to your browser and update ranking weights in real time.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 shadow-2xs">
          <Icon name="checkCircle" className="size-3.5 text-emerald-600" />
          Auto-Saved Locally
        </span>
      </header>

      <div className="space-y-8">
        {/* Basic Information */}
        <fieldset>
          <SectionLegend icon="file" label="Education & Contact" />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="profile-name" label="Full Name">
              <input
                id="profile-name"
                className={INPUT_CLASS}
                value={profile.name}
                onChange={(event) => update({ name: event.target.value })}
                placeholder="Aarav Sharma"
                autoComplete="name"
              />
            </Field>
            <Field id="profile-degree" label="Degree Program">
              <input
                id="profile-degree"
                className={INPUT_CLASS}
                value={profile.education.degree}
                onChange={(event) =>
                  updateEducation({ degree: event.target.value })
                }
                placeholder="B.Tech Computer Science"
              />
            </Field>
            <Field id="profile-college" label="College / University">
              <input
                id="profile-college"
                className={INPUT_CLASS}
                value={profile.education.college}
                onChange={(event) =>
                  updateEducation({ college: event.target.value })
                }
                placeholder="Indian Institute of Technology, Delhi"
              />
            </Field>
            <Field id="profile-year" label="Year of Study">
              <select
                id="profile-year"
                className={INPUT_CLASS}
                value={profile.education.year}
                onChange={(event) =>
                  updateEducation({ year: event.target.value })
                }
              >
                <option value="">Select your academic year</option>
                {yearOptions.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </fieldset>

        <SectionDivider />

        {/* Technical Skills */}
        <fieldset>
          <SectionLegend icon="zap" label="Technical Skills" />
          <ChipEditor
            id="profile-skills"
            values={profile.skills}
            placeholder="Type skill (e.g. Next.js, Python, PyTorch) and press Enter…"
            onChange={(values) => update({ skills: uniqueValues(values) })}
          />
          <p className="mt-2 text-xs text-slate-500">
            Skills are cross-referenced with role descriptions to compute direct fit percentages.
          </p>
        </fieldset>

        <SectionDivider />

        {/* Highlight Projects */}
        <fieldset>
          <SectionLegend icon="target" label="Featured Projects" />
          <div className="space-y-4">
            {profile.projects.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500">
                No projects added yet. Adding 1-2 projects significantly improves resume tailored bullets.
              </div>
            ) : null}
            {profile.projects.map((project, index) => (
              <div
                key={index}
                className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4.5 transition-all hover:border-slate-300 hover:bg-slate-50"
              >
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-800">
                    <span className="flex size-5 items-center justify-center rounded-full bg-blue-100 text-[10px] text-blue-700 font-bold">
                      {index + 1}
                    </span>
                    Project Details
                  </span>
                  <button
                    type="button"
                    onClick={() => removeProject(index)}
                    aria-label={`Remove project ${index + 1}`}
                    className="rounded-lg p-1 text-slate-400 transition-colors hover:bg-rose-100 hover:text-rose-700"
                  >
                    <Icon name="trash" className="size-4" />
                  </button>
                </div>
                <div className="space-y-3">
                  <input
                    aria-label={`Project ${index + 1} name`}
                    className={INPUT_CLASS}
                    value={project.name}
                    onChange={(event) =>
                      updateProject(index, { name: event.target.value })
                    }
                    placeholder="Project Title (e.g. Distributed Cache Engine)"
                  />
                  <textarea
                    aria-label={`Project ${index + 1} summary`}
                    rows={2}
                    className={cn(INPUT_CLASS, "resize-y text-xs")}
                    value={project.summary}
                    onChange={(event) =>
                      updateProject(index, { summary: event.target.value })
                    }
                    placeholder="Briefly state problem solved, architecture, and metrics (e.g. Reduced query latency by 45%)."
                  />
                  <input
                    aria-label={`Project ${index + 1} tech stack, comma separated`}
                    className={INPUT_CLASS}
                    value={project.tech.join(", ")}
                    onChange={(event) =>
                      updateProject(index, {
                        tech: event.target.value
                          .split(",")
                          .map((part) => part.trim())
                          .filter(Boolean),
                      })
                    }
                    placeholder="Technologies used (comma separated: Go, Redis, Docker, gRPC)"
                  />
                </div>
              </div>
            ))}
            <button
              type="button"
              onClick={addProject}
              className={buttonClass("secondary", "w-full py-2.5")}
            >
              <Icon name="plus" className="size-4" />
              Add Another Project
            </button>
          </div>
        </fieldset>

        <SectionDivider />

        {/* Experience & Roles */}
        <fieldset>
          <SectionLegend icon="building" label="Prior Experience & Hackathons" />
          <Field id="profile-experience" label="Experience highlights (one per line)">
            <textarea
              id="profile-experience"
              rows={3}
              className={cn(INPUT_CLASS, "resize-y leading-relaxed text-xs")}
              value={profile.experience.join("\n")}
              onChange={(event) =>
                update({
                  experience: event.target.value
                    .split("\n")
                    .map((line) => line.trim())
                    .filter(Boolean),
                })
              }
              placeholder={
                "Software Engineer Intern at Acme Labs (Summer 2025)\nFinalist, Smart India Hackathon 2024"
              }
            />
          </Field>
        </fieldset>

        <SectionDivider />

        {/* Target Opportunities */}
        <fieldset>
          <SectionLegend icon="filter" label="Target Opportunities" />
          <div className="flex flex-wrap gap-2">
            {LISTING_TYPES.map((type) => {
              const active = profile.target_types.includes(type);
              return (
                <button
                  key={type}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleTargetType(type)}
                  className={cn(
                    CHIP_CLASS,
                    "px-3.5 py-1.5 text-xs font-semibold shadow-2xs transition-all active:scale-[0.98]",
                    active
                      ? "border-blue-600 bg-blue-600 text-white"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50",
                  )}
                >
                  {active ? <Icon name="check" className="size-3" /> : null}
                  {titleCase(type)}
                </button>
              );
            })}
          </div>
        </fieldset>

        <SectionDivider />

        {/* Preferred Location */}
        <fieldset>
          <SectionLegend icon="mapPin" label="Work Mode & Location" />
          <Field id="profile-location" label="Preferred cities or Remote">
            <input
              id="profile-location"
              className={INPUT_CLASS}
              value={profile.location_pref}
              onChange={(event) => update({ location_pref: event.target.value })}
              placeholder="e.g. Remote, Bengaluru, Hyderabad, Pune, Mumbai"
            />
          </Field>
        </fieldset>
      </div>
    </div>
  );
}

function SectionLegend({
  icon,
  label,
}: {
  icon: IconName;
  label: string;
}) {
  return (
    <legend className="mb-3.5 flex items-center gap-2 text-sm font-bold text-slate-900">
      <span className="flex size-6 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
        <Icon name={icon} className="size-3.5" />
      </span>
      {label}
    </legend>
  );
}

function SectionDivider() {
  return <hr className="border-0 border-t border-slate-100" />;
}

function Field({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className={LABEL_CLASS}>
        {label}
      </label>
      {children}
    </div>
  );
}

function ChipEditor({
  id,
  values,
  placeholder,
  onChange,
}: {
  id: string;
  values: string[];
  placeholder: string;
  onChange: (next: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const inputId = `${id}-new`;

  function commit() {
    const value = draft.trim();
    if (!value) return;
    onChange([...values, value]);
    setDraft("");
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-2.5 min-h-8">
        {values.length === 0 ? (
          <p className="text-xs text-slate-400 py-1">No items added yet.</p>
        ) : null}
        {values.map((value, index) => (
          <span
            key={`${value}-${index}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50/80 px-3 py-1 text-xs font-semibold text-blue-800 shadow-2xs"
          >
            {value}
            <button
              type="button"
              onClick={() =>
                onChange(values.filter((_, valueIndex) => valueIndex !== index))
              }
              aria-label={`Remove ${value}`}
              className="rounded-full p-0.5 text-blue-600 hover:bg-blue-200/80 hover:text-blue-900 transition-colors"
            >
              <Icon name="x" className="size-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <label htmlFor={inputId} className="sr-only">
          Add new item
        </label>
        <input
          id={inputId}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              commit();
            }
          }}
          placeholder={placeholder}
          className={cn(INPUT_CLASS, "flex-1 text-xs")}
        />
        <button
          type="button"
          onClick={commit}
          disabled={!draft.trim()}
          className={buttonClass("secondary", "shrink-0 px-4")}
        >
          <Icon name="plus" className="size-3.5" />
          Add
        </button>
      </div>
    </div>
  );
}
