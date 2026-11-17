import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./styles/index.css";

import { onSessionEnded } from "./api/session";
import { LOGGED_OUT } from "./features/auth/api";
import { env } from "./env";
import { createQueryClient } from "./lib/query-client";
import { applyTheme, watchSystemTheme } from "./lib/theme";
import { createAppRouter } from "./router";

async function enableMocking(): Promise<void> {
  if (!import.meta.env.DEV || !env.apiMocking) return;
  const { worker } = await import("./mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass" });
}

applyTheme();
watchSystemTheme();

const queryClient = createQueryClient();
const router = createAppRouter(queryClient);
// 세션이 끝나면 다른 사용자의 데이터가 남지 않도록 캐시를 비운다 (decisions F19)
onSessionEnded((reason) => {
  queryClient.clear();
  // 쓰는 중에 세션이 끝나면(refresh 실패·다른 탭 로그아웃) 로그인 화면으로 보내 사유를 안내한다 (F19·F20)
  if (reason === LOGGED_OUT || router.state.location.pathname === "/login") return;
  void router.navigate({ to: "/login", search: { redirect: router.state.location.href }, replace: true });
});

await enableMocking();

const root = document.getElementById("root");
if (!root) throw new Error("#root 요소가 없습니다.");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
