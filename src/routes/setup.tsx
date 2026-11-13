import { createFileRoute } from "@tanstack/react-router";
import { Download } from "lucide-react";
import { Notice, PageHeader } from "@/components/nettime/ui";

export const Route = createFileRoute("/setup")({
  head: () => ({ meta: [{ title: "Controller setup — NetTime" }] }),
  component: SetupPage,
});

const ZIP = "nettime-pi-0.2.0.zip";
const guide = "https://github.com/polarvapourer/NetTime-Portfolio/blob/main/docs/SETUP.md";

function SetupPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Controller setup" intro="Run the controller on a Raspberry Pi connected to your home network. The planner stays separate from the controller dashboard." />
      <section className="panel space-y-4">
        <h2 className="font-semibold">Install the public controller package</h2>
        <p className="text-sm text-muted-foreground">Requires Python 3, systemd, SSH access and a compatible Linksys JNAP router in Deny mode. Use your own Pi username, hostname and router address.</p>
        <a href={`/downloads/${ZIP}`} download={ZIP} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"><Download className="size-4" />Download {ZIP}</a>
        <p className="text-sm">The package includes self-contained installation instructions. The <a className="text-primary underline" href={guide} target="_blank" rel="noreferrer">complete setup guide</a> also covers Wi-Fi setup without a keyboard, Windows commands, testing and recovery.</p>
      </section>
      <section className="panel space-y-3">
        <h2 className="font-semibold">Source installation on the Pi</h2>
        <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">{`git clone https://github.com/polarvapourer/NetTime-Portfolio.git
cd NetTime-Portfolio/controller
python3 -m nettime setup --router YOUR_ROUTER_ADDRESS
python3 -m nettime doctor
sh ./install-service.sh`}</pre>
        <p className="text-sm text-muted-foreground">Replace YOUR_ROUTER_ADDRESS before running setup. The router password is entered at a hidden prompt. Save the dashboard access key privately.</p>
      </section>
      <Notice>Fresh setup leaves blocking off. Validate the selected device and test both blocking and restoration on your own network before relying on enforcement.</Notice>
      <Notice>Export schedules from this planner and import them into the Pi dashboard. These interfaces do not sync automatically.</Notice>
    </div>
  );
}
