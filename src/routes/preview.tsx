import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Btn, Notice, PageHeader, Pill } from "@/components/nettime/ui";
import { useNetTime } from "@/lib/nettime/use-nettime";
import { DAY_LABELS, previewBonus, evaluatePolicy, formatMinutes, londonFromInstant, londonFromWallClock } from "@/lib/nettime/policy";

export const Route = createFileRoute("/preview")({
  head: () => ({ meta: [
    { title: "Policy preview — NetTime" },
    { name: "description", content: "Check what the saved rules would decide at any UK date and time." },
    { property: "og:title", content: "Policy preview — NetTime" },
    { property: "og:description", content: "Check what the saved rules would decide at any UK date and time." },
  ] }),
  component: PreviewPage,
});

const pad = (n: number) => String(n).padStart(2, "0");

function PreviewPage() {
  const { settings, bonus, ready, today, refreshToday } = useNetTime();
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [used, setUsed] = useState("0");
  const [includeBonus, setIncludeBonus] = useState(true);

  const setNow = () => {
    refreshToday();
    const t = londonFromInstant(new Date());
    setDate(t.date); setTime(`${pad(Math.floor(t.minuteOfDay / 60))}:${pad(t.minuteOfDay % 60)}`);
  };
  useEffect(setNow, []); // eslint-disable-line react-hooks/exhaustive-deps

  const at = londonFromWallClock(date, time);
  const usedN = Number(used);
  const usedOk = used !== "" && Number.isInteger(usedN) && usedN >= 0 && usedN <= 1440;
  const savedBonus = at && today ? previewBonus(bonus, at.date, today) : 0;
  const decision = ready && at && usedOk ? evaluatePolicy({ settings, at, usedMinutes: usedN, bonusMinutes: includeBonus ? savedBonus : 0 }) : null;
  const tone = !decision ? "muted" : decision.kind.startsWith("allow") ? "primary" : decision.kind === "setup-incomplete" ? "warning" : "danger";

  return (
    <div className="space-y-6">
      <PageHeader title="Policy preview" intro="Try the saved rules at any moment. This is a calculation only — it is not the real status of any device." />

      <section className="panel grid gap-5 md:grid-cols-2">
        <label className="flex flex-col gap-1.5 text-sm">Date (UK)
          <input type="date" className="field" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">Time (Europe/London)
          <input type="time" className="field" value={time} onChange={(e) => setTime(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">Leisure minutes already used that day
          <input type="number" min={0} max={1440} className="field" value={used} onChange={(e) => setUsed(e.target.value)} />
          {date && !at && <span className="text-destructive">Not a real calendar date.</span>}
          {!usedOk && <span className="text-destructive">Enter whole minutes, 0–1440.</span>}
        </label>
        <div className="flex flex-col justify-end gap-3 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" className="size-4 accent-primary" checked={includeBonus} onChange={(e) => setIncludeBonus(e.target.checked)} />
            Include today's saved "Add time" (only applies to the current UK date) ({savedBonus ? formatMinutes(savedBonus) : "none"})
          </label>
          <Btn variant="outline" onClick={setNow}>Use current UK time</Btn>
        </div>
      </section>

      <section className="panel space-y-3" aria-live="polite">
        <div className="flex flex-wrap items-center gap-3">
          <Pill tone={tone}>Policy preview</Pill>
          {at && <span className="text-sm text-muted-foreground">{DAY_LABELS[at.day]} {at.date} {time} UK</span>}
        </div>
        <p className="text-2xl font-semibold">{decision?.label ?? "Enter a date, time and minutes"}</p>
        {decision?.kind === "allow-remaining" && <p className="text-muted-foreground">{formatMinutes(decision.remaining)} left of {formatMinutes(decision.total)}.</p>}
        {decision?.kind === "allow-exception" && <p className="text-muted-foreground">Inside “{decision.window.label}” ({decision.window.start}–{decision.window.end}). These minutes don't count.</p>}
        {decision?.kind === "block-paused" && <p className="text-muted-foreground">Leisure access is paused. Exception windows still apply.</p>}
        {decision?.kind === "setup-incomplete" && <p className="text-muted-foreground">Choose an allowance for every day on the Schedule page.</p>}
      </section>

      <Notice>
        <strong className="text-foreground">How minutes would be counted.</strong> The separate controller counts minutes the {settings.deviceLabel} is connected with internet enabled, outside exception windows. That is <em>not</em> screen time — an idle connected device can still use minutes. The count resets at UK midnight. Nothing is being counted now.
      </Notice>
    </div>
  );
}
