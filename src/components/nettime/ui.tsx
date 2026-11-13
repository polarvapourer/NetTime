import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function PageHeader({ title, intro }: { title: string; intro?: ReactNode }) {
  return (
    <header className="mb-8">
      <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
      {intro && <p className="mt-2 max-w-2xl text-muted-foreground">{intro}</p>}
    </header>
  );
}

export function Pill({ tone = "muted", children }: { tone?: "muted" | "warning" | "primary" | "danger"; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium",
      tone === "muted" && "border-border bg-muted text-muted-foreground",
      tone === "warning" && "border-warning/40 bg-warning/10 text-warning",
      tone === "primary" && "border-primary/40 bg-primary/10 text-primary",
      tone === "danger" && "border-destructive/40 bg-destructive/10 text-destructive")}>{children}</span>
  );
}

export function Btn({ variant = "primary", className, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "outline" }) {
  return <button {...p} className={cn("inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50",
    variant === "primary" && "bg-primary text-primary-foreground hover:bg-primary/90",
    variant === "outline" && "border border-border bg-transparent hover:bg-secondary",
    variant === "ghost" && "hover:bg-secondary text-muted-foreground", className)} />;
}

export function Notice({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "warning" | "danger" | "primary" }) {
  return <div role={tone === "danger" ? "alert" : undefined} className={cn("rounded-lg border px-4 py-3 text-sm",
    tone === "muted" && "border-border bg-muted/60 text-muted-foreground",
    tone === "warning" && "border-warning/30 bg-warning/10 text-foreground",
    tone === "primary" && "border-primary/30 bg-primary/10 text-foreground",
    tone === "danger" && "border-destructive/40 bg-destructive/10 text-foreground")}>{children}</div>;
}
