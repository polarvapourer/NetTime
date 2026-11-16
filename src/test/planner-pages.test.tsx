import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { routeTree } from "@/routeTree.gen";
import { defaultSettings } from "@/lib/nettime/policy";
import { SETTINGS_KEY } from "@/lib/nettime/storage";

beforeEach(() => {
  localStorage.clear();
  const settings = defaultSettings();
  settings.deviceLabel = "Demo tablet";
  for (const day of Object.keys(settings.weekly) as (keyof typeof settings.weekly)[]) settings.weekly[day] = 60;
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
});
afterEach(cleanup);

async function open(path: string) {
  const router = createRouter({
    routeTree,
    context: { queryClient: new QueryClient() },
    history: createMemoryHistory({ initialEntries: [path] }),
    defaultPendingMinMs: 0,
  });
  await router.load();
  render(<RouterProvider router={router} />);
  return router;
}

describe("Standalone planner", () => {
  it.each(["/", "/schedule", "/preview", "/connection", "/data", "/setup"])("renders %s without an account or server integration", async (path) => {
    await open(path);
    expect(await screen.findByText("Planner preview — local only")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.queryByText("This page could not load.")).not.toBeInTheDocument();
  });

  it("updates the rendered decision at both exception boundaries", async () => {
    await open("/preview");
    const date = await screen.findByLabelText("Date (UK)");
    const time = screen.getByLabelText("Time (Europe/London)");
    fireEvent.change(date, { target: { value: "2030-06-15" } });
    fireEvent.change(screen.getByLabelText("Leisure minutes already used that day"), { target: { value: "150" } });
    fireEvent.change(time, { target: { value: "10:59" } });
    expect(await screen.findByText("Block — allowance exhausted")).toBeInTheDocument();
    fireEvent.change(time, { target: { value: "11:00" } });
    expect(await screen.findByText("Allow — scheduled exception")).toBeInTheDocument();
    fireEvent.change(time, { target: { value: "12:00" } });
    expect(await screen.findByText("Block — allowance exhausted")).toBeInTheDocument();
  });
});

describe("school and away controls", () => {
  it("saves schedules and restores them after reopening", async () => {
    const view = await open("/schedule");
    fireEvent.click(await screen.findByLabelText("Enable school hours"));
    fireEvent.change(screen.getByLabelText("School start"), { target: { value: "08:30" } });
    fireEvent.click(screen.getByRole("button", { name: "Add away period" }));
    fireEvent.change(screen.getByLabelText("Leave"), { target: { value: "17:00" } });
    fireEvent.change(screen.getByLabelText("Return"), { target: { value: "19:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Save schedule" }));
    expect(await screen.findByText("Saved on this browser")).toBeInTheDocument();
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY)!);
    expect(saved.schoolHours).toEqual({ enabled: true, start: "08:30", end: "15:00" });
    expect(saved.awayWindows[0]).toMatchObject({ enabled: true, start: "17:00", end: "19:00", days: ["mon", "tue", "wed", "thu", "fri"] });
    await view.navigate({ to: "/preview" }); cleanup(); await open("/schedule");
    expect(await screen.findByLabelText("Enable school hours")).toBeChecked();
    expect(screen.getByLabelText("School start")).toHaveValue("08:30");
    expect(screen.getByLabelText("Leave")).toHaveValue("17:00");
  });
  it("prevents invalid school hours from being saved", async () => {
    await open("/schedule");
    fireEvent.change(await screen.findByLabelText("School end"), { target: { value: "08:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Save schedule" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Fix the highlighted fields");
    expect(JSON.parse(localStorage.getItem(SETTINGS_KEY)!).schoolHours.end).toBe("15:00");
  });
});
