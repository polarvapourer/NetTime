import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/dom";
import { defaultSettings } from "@/lib/nettime/policy";

const staticPath = resolve("controller/nettime/static");

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); sessionStorage.clear(); document.body.innerHTML = ""; });

it("controller dashboard saves, reloads and removes school/away controls through the settings API", async () => {
  const html = readFileSync(resolve(staticPath, "index.html"), "utf8");
  document.body.innerHTML = html.match(/<body>([\s\S]*)<script/)![1]!;
  let settings = defaultSettings();
  const saved: unknown[] = [];
  sessionStorage.setItem("nettime.key", "test-dashboard-only");
  vi.stubGlobal("setInterval", vi.fn());
  vi.stubGlobal("fetch", vi.fn(async (path: string, options: RequestInit) => {
    if (path === "/api/settings") { settings = JSON.parse(String(options.body)).settings; saved.push(settings); }
    return { ok: true, status: 200, json: async () => path === "/api/status" ? {
      settings, status: {}, today: { date: "2026-11-16", usedSeconds: 0, decision: { label: "Setup incomplete" } },
      activationProblems: [], enforcement: false,
    } : { message: "Saved" } };
  }));
  new Function(readFileSync(resolve(staticPath, "app.js"), "utf8"))();
  await waitFor(() => expect(screen.getByLabelText("School start")).toHaveValue("09:00"));
  fireEvent.click(screen.getByLabelText("Enable school hours"));
  fireEvent.change(screen.getByLabelText("School start"), { target: { value: "08:30" } });
  fireEvent.click(screen.getByRole("button", { name: "Add away period" }));
  fireEvent.change(screen.getByLabelText("Leave"), { target: { value: "22:00" } });
  fireEvent.change(screen.getByLabelText("Return"), { target: { value: "07:00" } });
  fireEvent.click(screen.getByRole("button", { name: "Save schedule" }));
  await waitFor(() => expect(saved).toHaveLength(1));
  expect(settings.schoolHours).toEqual({ enabled: true, start: "08:30", end: "15:00" });
  expect(settings.awayWindows[0]).toMatchObject({ start: "22:00", end: "07:00", enabled: true });
  fireEvent.click(screen.getByRole("button", { name: "Remove away period" }));
  fireEvent.click(screen.getByRole("button", { name: "Save schedule" }));
  await waitFor(() => expect(saved).toHaveLength(2));
  expect(settings.awayWindows).toEqual([]);
});
