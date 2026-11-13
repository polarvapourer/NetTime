import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { londonFromWallClock, londonToday, previewBonus } from "./policy";
import { BONUS_KEY, loadBonus } from "./storage";
import { useNetTime } from "./use-nettime";

describe("calendar date validation", () => {
  it("rejects impossible dates instead of rolling over", () => {
    expect(londonFromWallClock("2026-02-31", "10:00")).toBeNull();
    expect(londonFromWallClock("2026-02-29", "10:00")).toBeNull();
    expect(londonFromWallClock("2026-13-01", "10:00")).toBeNull();
    expect(londonFromWallClock("2028-02-29", "10:00")?.day).toBe("tue");
  });
});

describe("London today with a fake clock (independent of process TZ)", () => {
  it("GMT: rolls at 00:00 UTC", () => {
    expect(londonToday(new Date("2026-11-16T23:59:59Z"))).toBe("2026-11-16");
    expect(londonToday(new Date("2026-11-17T00:00:00Z"))).toBe("2026-11-17");
  });
  it("BST: rolls at 23:00 UTC", () => {
    expect(londonToday(new Date("2026-07-10T22:59:59Z"))).toBe("2026-07-10");
    expect(londonToday(new Date("2026-07-10T23:00:00Z"))).toBe("2026-07-11");
  });
  it("preview bonus only for the current UK date", () => {
    const b = { date: "2026-07-10", minutes: 30 };
    expect(previewBonus(b, "2026-07-10", "2026-07-10")).toBe(30);
    expect(previewBonus(b, "2026-07-11", "2026-07-11")).toBe(0); // stale bonus
    expect(previewBonus(b, "2026-07-10", "2026-07-11")).toBe(0); // previewing a past date
  });
});

describe("useNetTime across UK midnight", () => {
  beforeEach(() => { localStorage.clear(); vi.useFakeTimers(); });
  afterEach(() => vi.useRealTimers());

  it("BST: open tab past midnight updates today, expires bonus, and Add time writes the new date", () => {
    vi.setSystemTime(new Date("2026-07-10T22:58:00Z")); // 23:58 BST
    const { result } = renderHook(() => useNetTime());
    expect(result.current.today).toBe("2026-07-10");
    act(() => result.current.addTimeToday(30));
    expect(loadBonus(localStorage)).toEqual({ date: "2026-07-10", minutes: 30 });

    vi.setSystemTime(new Date("2026-07-10T23:00:30Z")); // 00:00:30 BST next day
    act(() => { vi.advanceTimersByTime(30_000); });
    expect(result.current.today).toBe("2026-07-11");
    expect(result.current.bonus).toBeNull();
    expect(localStorage.getItem(BONUS_KEY)).toBeNull();
  });

  it("GMT: Add time click recomputes the date even before the interval fires", () => {
    vi.setSystemTime(new Date("2026-11-16T23:59:50Z"));
    const { result } = renderHook(() => useNetTime());
    expect(result.current.today).toBe("2026-11-16");
    vi.setSystemTime(new Date("2026-11-17T00:00:05Z"));
    act(() => result.current.addTimeToday(15));
    expect(loadBonus(localStorage)).toEqual({ date: "2026-11-17", minutes: 15 });
    expect(result.current.today).toBe("2026-11-17");
  });

  it("focus event refreshes the date", () => {
    vi.setSystemTime(new Date("2026-11-16T23:59:00Z"));
    const { result } = renderHook(() => useNetTime());
    vi.setSystemTime(new Date("2026-11-17T08:00:00Z"));
    act(() => { window.dispatchEvent(new Event("focus")); });
    expect(result.current.today).toBe("2026-11-17");
  });
});
