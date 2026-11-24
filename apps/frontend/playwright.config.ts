import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;
const isCI = Boolean(process.env.CI);

/**
 * 빌드 결과를 vite preview로 띄워 확인한다. 백엔드 API는 테스트에서 page.route로 모킹한다
 * (CI는 VITE_BACKEND_URL을 preview 주소로 두고 빌드한다 — .github/workflows/ci.yml).
 * CI는 앞 단계에서 한 번 빌드하므로 preview만 띄우고, 로컬은 빌드부터 한다.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  // CI는 E2E를 작업 하나에서 돌린다 (샤드 없음). 러너 코어를 모두 쓴다
  workers: isCI ? "100%" : undefined,
  reporter: isCI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: isCI ? "npm run preview" : "npm run build && npm run preview",
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !isCI,
    timeout: 120_000,
  },
});
