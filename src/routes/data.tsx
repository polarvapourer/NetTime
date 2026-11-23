import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Btn, Notice, PageHeader } from "@/components/nettime/ui";
import { useNetTime } from "@/lib/nettime/use-nettime";
import { exportSettingsJson, importSettingsJson, MAX_SETTINGS_BYTES } from "@/lib/nettime/storage";

export const Route = createFileRoute("/data")({
  head: () => ({ meta: [
    { title: "Import / Export — NetTime" },
    { name: "description", content: "Back up or restore NetTime schedule settings as a JSON file." },
    { property: "og:title", content: "Import / Export — NetTime" },
    { property: "og:description", content: "Back up or restore NetTime schedule settings as a JSON file." },
  ] }),
  component: DataPage,
});

function DataPage() {
  const { settings, save } = useNetTime();
  const [errors, setErrors] = useState<string[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  const doExport = () => {
    const blob = new Blob([exportSettingsJson(settings)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "nettime-settings.json"; a.click();
    URL.revokeObjectURL(a.href);
  };
  const onFile = async (f: File | undefined) => {
    setErrors([]); setMsg(null);
    if (!f) return;
    if (f.size > MAX_SETTINGS_BYTES) return setErrors(["Settings file exceeds 64 KiB."]);
    let text: string;
    try {
      text = await f.text();
    } catch {
      return setErrors(["Could not read the settings file."]);
    }
    const r = importSettingsJson(text);
    if (!r.ok) return setErrors(r.errors);
    save(r.settings); setMsg("Imported. Saved on this browser.");
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Import / Export" intro="Includes schema version, timezone, device label, weekly allowances, exception windows and the pause flag. No passwords. Today's added time is never included." />
      <section className="panel space-y-3">
        <h2 className="font-semibold">Export</h2>
        <Btn onClick={doExport}>Download settings</Btn>
      </section>
      <section className="panel space-y-3">
        <h2 className="font-semibold">Import</h2>
        <p className="text-sm text-muted-foreground">Replaces the current saved settings after the file is checked.</p>
        <input type="file" accept="application/json,.json" aria-label="Settings file" className="field text-sm" onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
        {msg && <Notice tone="primary">{msg}</Notice>}
        {errors.length > 0 && (
          <Notice tone="danger"><p className="font-medium">File not imported:</p>
            <ul className="mt-1 list-disc pl-5">{errors.map((e) => <li key={e}>{e}</li>)}</ul></Notice>
        )}
      </section>
    </div>
  );
}
