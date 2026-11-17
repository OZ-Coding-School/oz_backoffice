import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";

import { Toaster } from "@/components/ui/sonner";

export interface RouterContext {
  queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: function Root() {
    return (
      <>
        <Outlet />
        <Toaster />
      </>
    );
  },
  notFoundComponent: NotFound,
});

function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-2 bg-background px-4 text-center">
      <h1 className="text-h2 text-foreground">페이지를 찾을 수 없습니다</h1>
      <a href="/" className="text-body-strong text-primary-text hover:underline">
        홈으로
      </a>
    </main>
  );
}
