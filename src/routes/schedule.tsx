import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Btn, Notice, PageHeader, Pill } from "@/components/nettime/ui";
import { useNetTime } from "@/lib/nettime/use-nettime";
import { DAYS, DAY_LABELS, formatMinutes, validateException, type Day, type ExceptionWindow } from "@/lib/nettime/policy";

export const Route = createFileRoute("/schedule")({
  head: () => ({ meta: [
    { title: "Schedule — NetTime" },
    { name: "description", content: "Edit weekly internet allowances and the study exception window." },
    { property: "og:title", content: "Schedule — NetTime" },
    { property: "og:description", content: "Edit weekly internet allowances and the study exception window." },
  ] }),
  component: SchedulePage,
});

type Row = { h: string; m: string };
const toRow = (n: number | null): Row => n === null ? { h: "", m: "" } : { h: String(Math.floor(n / 60)), m: String(n % 60) };
function rowMinutes(r: Row): { value: number | null; error?: string } {
  if (r.h === "" && r.m === "") return { value: null };
  const h = r.h === "" ? 0 : Number(r.h), m = r.m === "" ? 0 : Number(r.m);
  if (!Number.isInteger(h) || !Number.isInteger(m) || h < 0 || m < 0 || m > 59) return { value: null, error: "Use whole hours and 0–59 minutes." };
  const t = h * 60 + m;
  if (t > 1440) return { value: null, error: "Cannot exceed 24h." };
  return { value: t };
}

function SchedulePage() {
  const { settings, save, ready, hasSaved } = useNetTime();
  const [rows, setRows] = useState<Record<Day, Row>>(() => Object.fromEntries(DAYS.map((d) => [d, toRow(null)])) as Record<Day, Row>);
  const [exceptions, setExceptions] = useState<ExceptionWindow[]>([]);
  const [bulk, setBulk] = useState({ wd: { h: "", m: "" }, we: { h: "", m: "" } });
  const [status, setStatus] = useState<"idle" | "saved" | "dirty">("idle");
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    setRows(Object.fromEntries(DAYS.map((d) => [d, toRow(settings.weekly[d])])) as Record<Day, Row>);
    setExceptions(settings.exceptions);
  }, [ready]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = () => { setStatus("dirty"); setFormError(null); };
  const setRow = (d: Day, r: Row) => { setRows((p) => ({ ...p, [d]: r })); dirty(); };
  const applyBulk = (which: "wd" | "we") => {
    const days: Day[] = which === "wd" ? ["mon", "tue", "wed", "thu", "fri"] : ["sat", "sun"];
    setRows((p) => ({ ...p, ...Object.fromEntries(days.map((d) => [d, { ...bulk[which] }])) }));
    dirty();
  };
  const updateEx = (i: number, patch: Partial<ExceptionWindow>) => { setExceptions((p) => p.map((e, j) => j === i ? { ...e, ...patch } : e)); dirty(); };

  const parsed = DAYS.map((d) => [d, rowMinutes(rows[d])] as const);
  const exErrors = exceptions.map(validateException);

  const onSave = () => {
    const missing = parsed.filter(([, r]) => r.value === null && !r.error).map(([d]) => DAY_LABELS[d]);
    if (parsed.some(([, r]) => r.error) || exErrors.some(Boolean)) return setFormError("Fix the highlighted fields first.");
    if (missing.length) return setFormError(`Choose an allowance for: ${missing.join(", ")}. Enter 0 for no leisure time.`);
    save({ ...settings, weekly: Object.fromEntries(parsed.map(([d, r]) => [d, r.value])) as Record<Day, number>, exceptions });
    setStatus("saved");
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Schedule" intro="Daily leisure allowance in UK time (Europe/London). Resets at UK midnight." />

      <section className="panel space-y-6">
        <h2 className="font-semibold">Weekly allowance</h2>
        <Notice>Every day starts unset. <strong>0</strong> means no leisure internet that day — only exception windows (like the study time) are allowed.</Notice>
        <div className="space-y-3 rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Fill several days at once</p>
          <BulkRow label="Weekdays" row={bulk.wd} onChange={(r) => setBulk((b) => ({ ...b, wd: r }))} onApply={() => applyBulk("wd")} />
          <BulkRow label="Weekend" row={bulk.we} onChange={(r) => setBulk((b) => ({ ...b, we: r }))} onApply={() => applyBulk("we")} />
        </div>
        <div className="divide-y divide-border">
          {parsed.map(([d, r]) => (
            <div key={d} className="flex flex-wrap items-center gap-3 py-3">
              <span className="w-28 font-medium">{DAY_LABELS[d]}</span>
              <TimeInputs row={rows[d]} onChange={(row) => setRow(d, row)} invalid={!!r.error} />
              <span className={r.error ? "text-sm text-destructive" : "text-sm text-muted-foreground"}>
                {r.error ?? (r.value === null ? "Not set" : r.value === 0 ? "No leisure time" : formatMinutes(r.value))}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">Exception windows</h2>
          <Pill tone="primary">Europe/London · BST/GMT automatic</Pill>
        </div>
        <p className="text-sm text-muted-foreground">
          Full internet is allowed during these windows, even when the allowance is used up or leisure is paused. Minutes inside never count against the allowance. At the end time, the remaining allowance resumes — or access is blocked if none is left. This does <strong>not</strong> limit access to study-related content; it's simply open internet for that time.
        </p>
        {exceptions.map((e, i) => (
          <div key={e.id} className="space-y-3 rounded-lg border border-border p-4">
            <input aria-label="Window name" className="field font-medium" value={e.label} maxLength={40} onChange={(ev) => updateEx(i, { label: ev.target.value })} />
            <div className="flex flex-wrap gap-2">
              {DAYS.map((d) => {
                const on = e.days.includes(d);
                return <Btn key={d} variant={on ? "primary" : "outline"} className="px-3" aria-pressed={on}
                  onClick={() => updateEx(i, { days: on ? e.days.filter((x) => x !== d) : DAYS.filter((x) => x === d || e.days.includes(x)) })}>{DAY_LABELS[d].slice(0, 3)}</Btn>;
              })}
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <label className="flex items-center gap-2">From <input type="time" className="field" value={e.start} onChange={(ev) => updateEx(i, { start: ev.target.value })} /></label>
              <label className="flex items-center gap-2">until <input type="time" className="field" value={e.end} onChange={(ev) => updateEx(i, { end: ev.target.value })} /></label>
              <span className="text-muted-foreground">(start included, end excluded)</span>
            </div>
            {exErrors[i] && <p className="text-sm text-destructive">{exErrors[i]}</p>}
          </div>
        ))}
      </section>

      <div className="sticky bottom-20 flex flex-wrap items-center gap-4 rounded-xl border border-border bg-card/95 p-4 backdrop-blur md:bottom-4">
        <Btn onClick={onSave}>Save schedule</Btn>
        <span className="text-sm text-muted-foreground">
          {status === "saved" ? "Saved on this browser" : status === "dirty" ? "Unsaved changes" : hasSaved ? "Saved on this browser" : "Not saved yet"}
        </span>
        <Pill>Not applied to a device</Pill>
        {formError && <p className="w-full text-sm text-destructive" role="alert">{formError}</p>}
      </div>
    </div>
  );
}

function BulkRow({ label, row, onChange, onApply }: { label: string; row: Row; onChange: (r: Row) => void; onApply: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="w-24 text-sm">{label}</span>
      <TimeInputs row={row} onChange={onChange} />
      <Btn variant="outline" onClick={onApply}>Apply</Btn>
    </div>
  );
}

function TimeInputs({ row, onChange, invalid }: { row: Row; onChange: (r: Row) => void; invalid?: boolean }) {
  const cls = `field w-20 ${invalid ? "border-destructive" : ""}`;
  return (
    <div className="flex items-center gap-2 text-sm">
      <input aria-label="Hours" inputMode="numeric" type="number" min={0} max={24} placeholder="h" className={cls} value={row.h} onChange={(e) => onChange({ ...row, h: e.target.value })} />
      <span className="text-muted-foreground">h</span>
      <input aria-label="Minutes" inputMode="numeric" type="number" min={0} max={59} placeholder="m" className={cls} value={row.m} onChange={(e) => onChange({ ...row, m: e.target.value })} />
      <span className="text-muted-foreground">m</span>
    </div>
  );
}
