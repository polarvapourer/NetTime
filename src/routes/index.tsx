import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Btn, Notice, PageHeader, Pill } from "@/components/nettime/ui";
import { useNetTime } from "@/lib/nettime/use-nettime";
import { DAY_LABELS, bonusFor, dayOfDate, formatMinutes, isSetupComplete } from "@/lib/nettime/policy";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [
    { title: "Dashboard — NetTime" },
    { name: "description", content: "Overview of the saved internet allowance schedule and owner actions." },
    { property: "og:title", content: "Dashboard — NetTime" },
    { property: "og:description", content: "Overview of the saved internet allowance schedule and owner actions." },
  ] }),
  component: Dashboard,
});

function Dashboard() {
  const { settings, save, bonus, addTimeToday, clearBonus, ready, today } = useNetTime();
  const [label, setLabel] = useState<string | null>(null);
  const [add, setAdd] = useState(15);
  const complete = isSetupComplete(settings);
  const todayDay = today ? dayOfDate(today) : null;
  const todayAllowance = todayDay ? settings.weekly[todayDay] : null;
  const todayBonus = today ? bonusFor(bonus, today) : 0;

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" />
      <section className="panel border-primary/30">
        <p className="text-lg leading-relaxed">Schedules are saved here. Internet blocking is not active until a gateway is connected.</p>
        <p className="mt-3 text-sm text-muted-foreground">Nothing on this page reaches the {settings.deviceLabel}. <Link to="/connection" className="text-primary underline-offset-4 hover:underline">What a gateway needs</Link></p>
      </section>

      {ready && !complete && (
        <Notice tone="warning">Setup incomplete — daily allowances haven't been chosen yet. <Link to="/schedule" className="font-medium text-primary hover:underline">Set the weekly schedule</Link></Notice>
      )}

      <div className="grid gap-6 md:grid-cols-3">
        <Metric title="Used today" />
        <Metric title="Remaining today" />
        <Metric title="Device status" />
      </div>

      <section className="panel space-y-4">
        <h2 className="font-semibold">Device</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1.5 text-sm">Label
            <input className="field" maxLength={40} value={label ?? settings.deviceLabel} onChange={(e) => setLabel(e.target.value)} />
          </label>
          <Btn variant="outline" disabled={label === null || !label.trim()} onClick={() => { save({ ...settings, deviceLabel: label!.trim() }); setLabel(null); }}>Save label</Btn>
        </div>
        <p className="text-sm text-muted-foreground">Not enrolled. No device discovery — this is just a name.</p>
      </section>

      <section className="panel space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">Owner actions</h2>
          <Pill>Not applied to a device</Pill>
        </div>
        <p className="text-sm text-muted-foreground">
          Today ({today && todayDay ? `${DAY_LABELS[todayDay]}, UK date ${today}` : "…"}): allowance{" "}
          {todayAllowance === null ? "not set" : formatMinutes(todayAllowance)}
          {todayBonus > 0 && <> + {formatMinutes(todayBonus)} added today</>}.
        </p>

        <div className="space-y-2">
          <h3 className="text-sm font-medium">Add time (today only)</h3>
          <div className="flex flex-wrap items-center gap-2">
            {[15, 30, 60].map((m) => (
              <Btn key={m} variant={add === m ? "primary" : "outline"} onClick={() => setAdd(m)}>+{m}m</Btn>
            ))}
            <Btn disabled={!today} onClick={() => addTimeToday(add)}>Add {add} minutes</Btn>
            {todayBonus > 0 && <Btn variant="ghost" onClick={clearBonus}>Clear today's extra</Btn>}
          </div>
          <p className="text-xs text-muted-foreground">Expires at UK midnight. Never carried into tomorrow or exported.</p>
        </div>

        <div className="space-y-2 border-t border-border pt-5">
          <h3 className="text-sm font-medium">Pause leisure access</h3>
          <div className="flex flex-wrap items-center gap-3">
            <Btn variant={settings.leisurePaused ? "outline" : "primary"} onClick={() => save({ ...settings, leisurePaused: !settings.leisurePaused })}>
              {settings.leisurePaused ? "Resume leisure access" : "Pause leisure access"}
            </Btn>
            <span className="text-sm">{settings.leisurePaused ? "Paused (rule saved)" : "Not paused"}</span>
          </div>
          <p className="text-xs text-muted-foreground">Stays on until you turn it off. The study window still allows internet while paused.</p>
        </div>

        <p className="text-sm"><Link to="/schedule" className="text-primary hover:underline">Change daily limits →</Link></p>
      </section>
    </div>
  );
}

function Metric({ title }: { title: string }) {
  return (
    <div className="panel">
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className="mt-2 font-medium">Unavailable — connect a gateway</p>
    </div>
  );
}
