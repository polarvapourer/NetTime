import { Link } from "@tanstack/react-router";
import { CalendarClock, FileJson, Gauge, PlugZap, SearchCheck } from "lucide-react";
import type { ReactNode } from "react";
import { Pill } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: Gauge },
  { to: "/schedule", label: "Schedule", icon: CalendarClock },
  { to: "/preview", label: "Preview", icon: SearchCheck },
  { to: "/connection", label: "Connection", icon: PlugZap },
  { to: "/data", label: "Import/Export", icon: FileJson },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen md:flex">
      <aside className="hidden w-60 shrink-0 border-r border-sidebar-border bg-sidebar md:flex md:flex-col">
        <div className="px-6 py-7 text-lg font-semibold tracking-tight text-sidebar-foreground">NetTime</div>
        <nav className="flex flex-col gap-1 px-3">
          {NAV.map(({ to, label, icon: Icon }) => (
            <Link key={to} to={to} activeOptions={{ exact: to === "/" }}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-sidebar-foreground/80 hover:bg-sidebar-accent"
              activeProps={{ className: "bg-sidebar-accent text-sidebar-accent-foreground" }}>
              <Icon className="size-4" /> {label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-border px-5 py-4 md:px-10">
          <span className="text-lg font-semibold md:hidden">NetTime</span>
          <span className="hidden md:block" />
          <Pill tone="warning"><span className="size-1.5 rounded-full bg-warning" />Planner preview — local only</Pill>
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-5 pb-28 pt-8 md:px-10 md:pb-12">{children}</main>
      </div>
      <nav className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-5 border-t border-sidebar-border bg-sidebar md:hidden">
        {NAV.map(({ to, label, icon: Icon }) => (
          <Link key={to} to={to} activeOptions={{ exact: to === "/" }}
            className="flex flex-col items-center gap-1 py-2.5 text-[11px] text-sidebar-foreground/70"
            activeProps={{ className: "text-primary" }}>
            <Icon className="size-5" />{label.split("/")[0]}
          </Link>
        ))}
      </nav>
    </div>
  );
}
