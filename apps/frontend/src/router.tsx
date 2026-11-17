import type { QueryClient } from "@tanstack/react-query";
import { createRouter, type RouterHistory } from "@tanstack/react-router";

import { PendingScreen } from "./components/pending-screen";
import { routeTree } from "./routeTree.gen";

export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  return createRouter({
    routeTree,
    context: { queryClient },
    defaultPreload: "intent",
    // 데이터 신선도는 TanStack Query가 관리한다
    defaultPreloadStaleTime: 0,
    scrollRestoration: true,
    defaultPendingMs: 300,
    defaultPendingMinMs: 300,
    defaultPendingComponent: PendingScreen,
    ...(history ? { history } : {}),
  });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
