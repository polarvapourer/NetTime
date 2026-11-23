import { createFileRoute } from "@tanstack/react-router";
import { Download } from "lucide-react";
import { Notice, PageHeader } from "@/components/nettime/ui";

export const Route = createFileRoute("/setup")({
  head: () => ({ meta: [{ title: "Controller setup — NetTime" }] }),
  component: SetupPage,
});

const ZIP = "nettime-controller-1.3.0.zip";
const guide = "https://github.com/polarvapourer/NetTime/blob/main/docs/SETUP.md";
const routers = "https://github.com/polarvapourer/NetTime/blob/main/controller/ROUTERS.md";

function SetupPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Controller setup" intro="Build and manage NetTime from Windows, Linux or macOS on Apple Silicon or Intel. Run the controller on that computer or on a separate always-on device." />
      <section className="panel space-y-4">
        <h2 className="font-semibold">Choose your controller</h2>
        <p className="text-sm text-muted-foreground">An always-on PC, Mac, Linux server, mini PC or Raspberry Pi can run the Python controller. It needs Python 3, private local storage and access to a compatible router. Keep it awake and connected over Wi-Fi or Ethernet.</p>
        <a href={`/downloads/${ZIP}`} download={ZIP} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"><Download className="size-4" />Download {ZIP}</a>
        <p className="text-sm">The same source package works on all supported host platforms. Follow the <a className="text-primary underline" href={guide} target="_blank" rel="noreferrer">setup guide</a> for building, transferring files, background startup and remote dashboard access.</p>
      </section>
      <section className="panel space-y-3">
        <h2 className="font-semibold">Start on the controller</h2>
        <p className="text-sm text-muted-foreground">Enter the extracted package directory, or NetTime/controller in a source checkout. These examples use the built-in Linksys adapter.</p>
        <h3 className="text-sm font-medium">Windows PowerShell</h3>
        <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">{`py -3 -m nettime setup --router YOUR_ROUTER_ADDRESS
py -3 -m nettime doctor
py -3 -m nettime serve`}</pre>
        <h3 className="text-sm font-medium">macOS (Apple Silicon or Intel) / Linux / Raspberry Pi</h3>
        <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">{`python3 -m nettime setup --router YOUR_ROUTER_ADDRESS
python3 -m nettime doctor
python3 -m nettime serve`}</pre>
        <p className="text-sm text-muted-foreground">Replace YOUR_ROUTER_ADDRESS. The router password is entered at a hidden prompt. Save the dashboard key privately. Open 127.0.0.1:8787 on the controller, or use an SSH tunnel from your management computer.</p>
      </section>
      <section className="panel space-y-3">
        <h2 className="font-semibold">Check the router separately</h2>
        <p className="text-sm text-muted-foreground">The built-in adapter has been checked on a Linksys/Community Fibre M60CF-EU. Another brand needs a compatible, validated adapter for its management interface. Some routers cannot be controlled externally.</p>
        <a className="text-sm text-primary underline" href={routers} target="_blank" rel="noreferrer">Router compatibility and adapter instructions</a>
      </section>
      <Notice>Fresh setup leaves blocking off. Test actual blocking and restoration on your own network before relying on enforcement.</Notice>
      <Notice>Export schedules from this planner and import them into the controller dashboard. These interfaces do not sync automatically.</Notice>
    </div>
  );
}
