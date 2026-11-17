import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./styles/index.css";

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
