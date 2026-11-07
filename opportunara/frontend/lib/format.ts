const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/**
 * Format an API date ("2026-12-01" or an ISO timestamp) without constructing a
 * `Date`. Doing the maths from the string keeps rendering pure (no timezone or
 * clock dependence), which matters for hydration and for the react-hooks purity
 * lint rules.
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "Date to be confirmed";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  const [, year, month, day] = match;
  const monthIndex = Number(month) - 1;
  const monthName = MONTHS[monthIndex] ?? month;
  return `${Number(day)} ${monthName} ${year}`;
}

export type DeadlineTone = "expired" | "today" | "urgent" | "warn" | "calm";

export interface DeadlineInfo {
  text: string;
  tone: DeadlineTone;
}

/** Human countdown copy. `days_left` comes from the API so no clock is read. */
export function deadlineInfo(
  daysLeft: number,
  expired: boolean,
): DeadlineInfo {
  if (expired || daysLeft < 0) {
    return { text: "Expired", tone: "expired" };
  }
  if (daysLeft === 0) {
    return { text: "Expires today", tone: "today" };
  }
  if (daysLeft === 1) {
    return { text: "1 day left", tone: "urgent" };
  }
  if (daysLeft <= 7) {
    return { text: `${daysLeft} days left`, tone: "urgent" };
  }
  if (daysLeft <= 14) {
    return { text: `${daysLeft} days left`, tone: "warn" };
  }
  return { text: `${daysLeft} days left`, tone: "calm" };
}

/** Only used for static strings in the UI, e.g. "60 listings". */
export function formatCount(value: number): string {
  return new Intl.NumberFormat("en-IN").format(value);
}
