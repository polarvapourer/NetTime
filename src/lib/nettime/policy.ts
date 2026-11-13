// Pure, typed NetTime policy logic. No browser APIs, no browser-timezone dependence.
export const TIMEZONE = "Europe/London" as const;
export const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export type Day = (typeof DAYS)[number];
export const DAY_LABELS: Record<Day, string> = {
  mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday",
  fri: "Friday", sat: "Saturday", sun: "Sunday",
};
export const MAX_DAY_MINUTES = 1440;

/** Minutes of leisure allowance per day; null = not configured yet. */
export type WeeklyAllowance = Record<Day, number | null>;

/** Start inclusive, end exclusive, same day, "HH:MM" London wall time. */
export interface ExceptionWindow { id: string; label: string; days: Day[]; start: string; end: string }

export interface NetTimeSettings {
  schemaVersion: 1;
  timezone: typeof TIMEZONE;
  deviceLabel: string;
  weekly: WeeklyAllowance;
  exceptions: ExceptionWindow[];
  leisurePaused: boolean;
}

/** Today-only extra allowance, scoped to a London calendar date. */
export interface DailyBonus { date: string; minutes: number }

export function defaultSettings(): NetTimeSettings {
  return {
    schemaVersion: 1,
    timezone: TIMEZONE,
    deviceLabel: "iPad",
    weekly: { mon: null, tue: null, wed: null, thu: null, fri: null, sat: null, sun: null },
    exceptions: [{ id: "study", label: "Study time", days: ["sat", "sun"], start: "11:00", end: "12:00" }],
    leisurePaused: false,
  };
}

export function parseHHMM(v: string): number | null {
  const m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(v);
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

export function validateAllowanceMinutes(n: unknown): string | null {
  if (typeof n !== "number" || !Number.isInteger(n)) return "Must be a whole number of minutes.";
  if (n < 0 || n > MAX_DAY_MINUTES) return "Must be between 0 and 24 hours (0–1440 minutes).";
  return null;
}

export function validateException(e: Pick<ExceptionWindow, "days" | "start" | "end">): string | null {
  if (e.days.length === 0) return "Choose at least one day.";
  const s = parseHHMM(e.start), en = parseHHMM(e.end);
  if (s === null || en === null) return "Times must be HH:MM (24-hour).";
  if (s === en) return "Start and end cannot be the same.";
  if (s > en) return "End must be after start. Windows that cross midnight are not supported — split it into two windows.";
  return null;
}

export function isSetupComplete(s: NetTimeSettings): boolean {
  return DAYS.every((d) => s.weekly[d] !== null && validateAllowanceMinutes(s.weekly[d]) === null);
}

/** A moment expressed as Europe/London wall-clock time. */
export interface LondonTime { date: string; day: Day; minuteOfDay: number }

/** Day of week for a calendar date string, independent of any timezone. */
export function dayOfDate(date: string): Day {
  const [y = 0, m = 1, d = 1] = date.split("-").map(Number);
  const js = new Date(Date.UTC(y, m - 1, d)).getUTCDay(); // 0 = Sunday
  return DAYS[(js + 6) % 7] as Day;
}

/** True only for real Gregorian dates (rejects e.g. 2026-02-31 instead of rolling over). */
export function isValidCalendarDate(date: string): boolean {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!m) return false;
  const y = Number(m[1]), mo = Number(m[2]), d = Number(m[3]);
  const dt = new Date(Date.UTC(y, mo - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d;
}

export function londonFromWallClock(date: string, time: string): LondonTime | null {
  if (!isValidCalendarDate(date)) return null;
  const mins = parseHHMM(time);
  if (mins === null) return null;
  return { date, day: dayOfDate(date), minuteOfDay: mins };
}

/** Convert an absolute instant to London wall time (handles BST/GMT). */
export function londonFromInstant(instant: Date): LondonTime {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: TIMEZONE, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(instant);
  const g = (t: string) => parts.find((p) => p.type === t)!.value;
  const date = `${g("year")}-${g("month")}-${g("day")}`;
  return { date, day: dayOfDate(date), minuteOfDay: Number(g("hour")) * 60 + Number(g("minute")) };
}

export function activeException(s: NetTimeSettings, t: LondonTime): ExceptionWindow | null {
  return s.exceptions.find((e) => {
    const a = parseHHMM(e.start), b = parseHHMM(e.end);
    return a !== null && b !== null && a < b && e.days.includes(t.day) && t.minuteOfDay >= a && t.minuteOfDay < b;
  }) ?? null;
}

/** Current Europe/London calendar date for an instant (default: now). */
export function londonToday(now: Date = new Date()): string {
  return londonFromInstant(now).date;
}

/** Bonus usable at a previewed date: only when that date IS the current UK date and the bonus belongs to it. */
export function previewBonus(bonus: DailyBonus | null, previewDate: string, currentDate: string): number {
  return previewDate === currentDate ? bonusFor(bonus, currentDate) : 0;
}

export function bonusFor(bonus: DailyBonus | null, date: string): number {
  return bonus && bonus.date === date ? bonus.minutes : 0;
}

export type Decision =
  | { kind: "setup-incomplete"; label: "Setup incomplete" }
  | { kind: "allow-exception"; label: "Allow — scheduled exception"; window: ExceptionWindow }
  | { kind: "block-paused"; label: "Block — leisure paused" }
  | { kind: "allow-remaining"; label: "Allow — allowance remaining"; remaining: number; total: number }
  | { kind: "block-exhausted"; label: "Block — allowance exhausted"; total: number };

/**
 * usedMinutes = internet-enabled connected minutes outside exception windows,
 * counted since London midnight of `t.date`. It is NOT screen time.
 */
export function evaluatePolicy(input: {
  settings: NetTimeSettings; at: LondonTime; usedMinutes: number; bonusMinutes?: number;
}): Decision {
  const { settings, at } = input;
  if (!isSetupComplete(settings)) return { kind: "setup-incomplete", label: "Setup incomplete" };
  const win = activeException(settings, at);
  if (win) return { kind: "allow-exception", label: "Allow — scheduled exception", window: win };
  if (settings.leisurePaused) return { kind: "block-paused", label: "Block — leisure paused" };
  const total = (settings.weekly[at.day] ?? 0) + Math.max(0, input.bonusMinutes ?? 0);
  const remaining = total - Math.max(0, input.usedMinutes);
  return remaining > 0
    ? { kind: "allow-remaining", label: "Allow — allowance remaining", remaining, total }
    : { kind: "block-exhausted", label: "Block — allowance exhausted", total };
}

export function formatMinutes(n: number): string {
  const h = Math.floor(n / 60), m = n % 60;
  return h && m ? `${h}h ${m}m` : h ? `${h}h` : `${m}m`;
}
