/// <reference types="vitest/config" />
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  // 라우터 플러그인은 react 플러그인보다 먼저 둔다 (src/routes → src/routeTree.gen.ts)
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
      // 경로 폴더 안의 테스트 파일은 라우트로 보지 않는다
      routeFileIgnorePattern: "\\.test\\.tsx?$",
    }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // 백엔드 CORS_ORIGINS·FRONTEND_BASE_URL 기본값과 같은 포트
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
