import { z } from "zod";
import { DAYS, TIMEZONE, defaultSettings, validateException, type DailyBonus, type NetTimeSettings } from "./policy";

export const SETTINGS_KEY = "nettime.settings.v1";
export const BONUS_KEY = "nettime.bonus.v1";

const dayEnum = z.enum(DAYS);
const minutes = z.number().int("Allowance must be whole minutes").min(0).max(1440, "Allowance cannot exceed 1440 minutes");

export const settingsSchema = z.object({
  schemaVersion: z.literal(1, { errorMap: () => ({ message: "Unsupported schemaVersion (expected 1)" }) }),
  timezone: z.literal(TIMEZONE, { errorMap: () => ({ message: `timezone must be "${TIMEZONE}"` }) }),
  deviceLabel: z.string().trim().min(1).max(40),
  weekly: z.object(Object.fromEntries(DAYS.map((d) => [d, minutes.nullable()])) as Record<(typeof DAYS)[number], z.ZodNullable<typeof minutes>>).strict(),
  exceptions: z.array(z.object({
    id: z.string().min(1), label: z.string().min(1).max(40),
    days: z.array(dayEnum), start: z.string(), end: z.string(),
  }).strict().superRefine((e, ctx) => {
    const err = validateException(e);
    if (err) ctx.addIssue({ code: z.ZodIssueCode.custom, message: `Exception "${e.label}": ${err}` });
  })).max(10),
  leisurePaused: z.boolean(),
}).strict();

export type ParseResult = { ok: true; settings: NetTimeSettings } | { ok: false; errors: string[] };

export function parseSettings(raw: unknown): ParseResult {
  const r = settingsSchema.safeParse(raw);
  if (r.success) return { ok: true, settings: r.data as NetTimeSettings };
  return { ok: false, errors: r.error.issues.map((i) => `${i.path.join(".") || "file"}: ${i.message}`) };
}

export function importSettingsJson(text: string): ParseResult {
  let raw: unknown;
  try { raw = JSON.parse(text); } catch { return { ok: false, errors: ["File is not valid JSON."] }; }
  return parseSettings(raw);
}

/** Export only the weekly rules. Today's bonus is deliberately excluded. */
export function exportSettingsJson(s: NetTimeSettings): string {
  const { schemaVersion, timezone, deviceLabel, weekly, exceptions, leisurePaused } = s;
  return JSON.stringify({ schemaVersion, timezone, deviceLabel, weekly, exceptions, leisurePaused }, null, 2);
}

export function loadSettings(storage: Storage): NetTimeSettings {
  const text = storage.getItem(SETTINGS_KEY);
  if (!text) return defaultSettings();
  const r = importSettingsJson(text);
  return r.ok ? r.settings : defaultSettings();
}

export function saveSettings(storage: Storage, s: NetTimeSettings) {
  storage.setItem(SETTINGS_KEY, exportSettingsJson(s));
}

export function loadBonus(storage: Storage): DailyBonus | null {
  try {
    const b = JSON.parse(storage.getItem(BONUS_KEY) ?? "null");
    if (b && typeof b.date === "string" && Number.isInteger(b.minutes) && b.minutes > 0) return b;
  } catch { /* ignore */ }
  return null;
}

export function saveBonus(storage: Storage, b: DailyBonus | null) {
  if (b) storage.setItem(BONUS_KEY, JSON.stringify(b)); else storage.removeItem(BONUS_KEY);
}

/** Add minutes to today's bonus; a bonus from another date is discarded, never carried over. */
export function addBonus(current: DailyBonus | null, today: string, add: number): DailyBonus {
  const base = current && current.date === today ? current.minutes : 0;
  return { date: today, minutes: Math.min(1440, base + add) };
}
