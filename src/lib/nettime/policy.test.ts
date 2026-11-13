import { describe, expect, it } from "vitest";
import { defaultSettings, evaluatePolicy, londonFromInstant, londonFromWallClock, validateException, type NetTimeSettings } from "./policy";
import { addBonus, exportSettingsJson, importSettingsJson } from "./storage";
import { bonusFor } from "./policy";

function configured(mins = 60): NetTimeSettings {
  const s = defaultSettings();
  for (const d of Object.keys(s.weekly) as (keyof typeof s.weekly)[]) s.weekly[d] = mins;
  return s;
}
const at = (date: string, time: string) => londonFromWallClock(date, time)!;
// 2026-11-14 is a Saturday, 2026-11-15 Sunday, 2026-11-16 Monday.

describe("study exception with zero remaining", () => {
  const s = configured(60);
  const ev = (time: string, date = "2026-11-14") => evaluatePolicy({ settings: s, at: at(date, time), usedMinutes: 60 }).kind;
  it("10:59 Saturday blocks", () => expect(ev("10:59")).toBe("block-exhausted"));
  it("11:00 Saturday allows (inclusive)", () => expect(ev("11:00")).toBe("allow-exception"));
  it("11:59 Sunday allows", () => expect(ev("11:59", "2026-11-15")).toBe("allow-exception"));
  it("12:00 Sunday blocks (exclusive end)", () => expect(ev("12:00", "2026-11-15")).toBe("block-exhausted"));
  it("weekday 11:00 has no exception", () => expect(ev("11:00", "2026-11-16")).toBe("block-exhausted"));
  it("study window overrides leisure pause", () => {
    const p = { ...s, leisurePaused: true };
    expect(evaluatePolicy({ settings: p, at: at("2026-11-14", "11:30"), usedMinutes: 0 }).kind).toBe("allow-exception");
    expect(evaluatePolicy({ settings: p, at: at("2026-11-14", "12:00"), usedMinutes: 0 }).kind).toBe("block-paused");
  });
});

describe("allowance boundary", () => {
  const s = configured(90);
  it("89 used of 90 allows with 1 remaining", () => {
    const d = evaluatePolicy({ settings: s, at: at("2026-11-16", "11:00"), usedMinutes: 89 });
    expect(d.kind).toBe("allow-remaining");
    if (d.kind === "allow-remaining") expect(d.remaining).toBe(1);
  });
  it("90 used of 90 blocks", () => expect(evaluatePolicy({ settings: s, at: at("2026-11-16", "11:00"), usedMinutes: 90 }).kind).toBe("block-exhausted"));
  it("0 allowance blocks immediately", () => expect(evaluatePolicy({ settings: configured(0), at: at("2026-11-16", "09:00"), usedMinutes: 0 }).kind).toBe("block-exhausted"));
  it("today's bonus extends the limit only on its date", () => {
    const b = { date: "2026-11-16", minutes: 30 };
    expect(evaluatePolicy({ settings: s, at: at("2026-11-16", "20:00"), usedMinutes: 100, bonusMinutes: bonusFor(b, "2026-11-16") }).kind).toBe("allow-remaining");
    expect(evaluatePolicy({ settings: s, at: at("2026-11-17", "20:00"), usedMinutes: 100, bonusMinutes: bonusFor(b, "2026-11-17") }).kind).toBe("block-exhausted");
  });
  it("adding time on a new day discards yesterday's bonus", () => {
    expect(addBonus({ date: "2026-11-16", minutes: 30 }, "2026-11-17", 15)).toEqual({ date: "2026-11-17", minutes: 15 });
  });
});

describe("setup", () => {
  it("unconfigured defaults return Setup incomplete, even in the study window", () => {
    expect(evaluatePolicy({ settings: defaultSettings(), at: at("2026-11-14", "11:30"), usedMinutes: 0 }).kind).toBe("setup-incomplete");
  });
  it("one missing day keeps setup incomplete", () => {
    const s = configured(60); s.weekly.wed = null;
    expect(evaluatePolicy({ settings: s, at: at("2026-11-16", "09:00"), usedMinutes: 0 }).kind).toBe("setup-incomplete");
  });
  it("rejects cross-midnight and reversed windows", () => {
    expect(validateException({ days: ["sat"], start: "23:00", end: "01:00" })).toMatch(/midnight/);
    expect(validateException({ days: ["sat"], start: "11:00", end: "12:00" })).toBeNull();
  });
});

describe("Europe/London timezone", () => {
  it("summer (BST): 10:30 UTC is 11:30 London → study", () => {
    const t = londonFromInstant(new Date("2026-07-11T10:30:00Z"));
    expect(t).toEqual({ date: "2026-07-11", day: "sat", minuteOfDay: 690 });
    expect(evaluatePolicy({ settings: configured(0), at: t, usedMinutes: 0 }).kind).toBe("allow-exception");
  });
  it("summer (BST): 11:00 UTC is 12:00 London → blocked", () => {
    expect(evaluatePolicy({ settings: configured(0), at: londonFromInstant(new Date("2026-07-11T11:00:00Z")), usedMinutes: 0 }).kind).toBe("block-exhausted");
  });
  it("winter (GMT): 11:30 UTC is 11:30 London", () => {
    expect(londonFromInstant(new Date("2026-11-14T11:30:00Z")).minuteOfDay).toBe(690);
  });
  it("clock-change Sunday 29 Mar 2026: 10:15 UTC = 11:15 BST → study", () => {
    const t = londonFromInstant(new Date("2026-03-29T10:15:00Z"));
    expect(t.day).toBe("sun"); expect(t.minuteOfDay).toBe(675);
  });
  it("daily reset at London midnight: 23:30 UTC in summer is next day in London", () => {
    expect(londonFromInstant(new Date("2026-07-10T23:30:00Z")).date).toBe("2026-07-11");
  });
});

describe("import/export", () => {
  it("round-trips without a daily bonus field", () => {
    const json = exportSettingsJson(configured(45));
    expect(json).not.toMatch(/bonus/i);
    expect(importSettingsJson(json).ok).toBe(true);
  });
  it("rejects bad schema, totals over 1440, and stray bonus fields", () => {
    const base = JSON.parse(exportSettingsJson(configured(45)));
    expect(importSettingsJson("nope").ok).toBe(false);
    expect(importSettingsJson(JSON.stringify({ ...base, schemaVersion: 2 })).ok).toBe(false);
    expect(importSettingsJson(JSON.stringify({ ...base, weekly: { ...base.weekly, mon: 1441 } })).ok).toBe(false);
    expect(importSettingsJson(JSON.stringify({ ...base, bonus: { minutes: 30 } })).ok).toBe(false);
  });
});
