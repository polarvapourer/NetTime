import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRootRouteWithContext, HeadContent, Link, Outlet } from "@tanstack/react-router";
import { AppShell } from "@/components/nettime/AppShell";

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({ meta: [{ title: "NetTime" }] }),
  component: RootComponent,
  notFoundComponent: () => <main className="p-10"><h1>Page not found</h1><Link to="/">Return to NetTime</Link></main>,
  errorComponent: () => <main className="p-10"><h1>This page could not load.</h1><a href="/">Reload NetTime</a></main>,
});

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  return (
    <QueryClientProvider client={queryClient}>
      <HeadContent />
      <AppShell><Outlet /></AppShell>
    </QueryClientProvider>
  );
}
