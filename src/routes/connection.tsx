import { createFileRoute, Link } from "@tanstack/react-router";
import { Notice, PageHeader, Pill } from "@/components/nettime/ui";

export const Route = createFileRoute("/connection")({
  head: () => ({ meta: [{ title: "Controller connection — NetTime" }] }),
  component: ConnectionPage,
});

function ConnectionPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Controller connection" intro="This planner stores settings in your browser. It has no connection to a device, router or account." />
      <section className="panel flex flex-wrap items-center gap-3"><Pill tone="warning">Planner preview</Pill><span className="text-sm text-muted-foreground">No real usage is measured and no network rules are changed here.</span></section>
      <section className="panel space-y-3">
        <h2 className="font-semibold">Enforcement runs on your controller device</h2>
        <p className="text-sm text-muted-foreground">The separate Python controller reads a compatible router's device list, counts connected-and-allowed time and manages one selected MAC-filter entry. It has its own loopback-only dashboard, opened locally or reached through SSH from another computer.</p>
        <Link to="/setup" className="text-sm font-medium text-primary underline">Open controller setup</Link>
      </section>
      <section className="panel space-y-3">
        <h2 className="font-semibold">Check compatibility first</h2>
        <p className="text-sm text-muted-foreground">The adapter was checked with a Linksys/Community Fibre M60CF-EU router. Other brands need a driver for their actual management interface; other models and firmware need separate validation. It requires Deny mode and a stable per-network address for the selected device.</p>
        <p className="text-sm text-muted-foreground">The controller device must remain powered and connected. Rules apply only on the controlled network. This does not measure screen time, filter particular websites or create a Wi-Fi extender.</p>
      </section>
      <Notice>Router passwords belong only in the controller's hidden setup prompt. This browser planner does not request them.</Notice>
    </div>
  );
}
