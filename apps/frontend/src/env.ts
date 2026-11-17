/** 빌드 시점 환경 값 (`VITE_*`, .env.example 참고). */
const backendUrl = (import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000").replace(/\/+$/, "");

export const env = {
  backendUrl,
  apiBaseUrl: `${backendUrl}/api/v1`,
  apiMocking: import.meta.env.VITE_API_MOCKING === "true",
} as const;
