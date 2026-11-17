import createClient, { type Middleware } from "openapi-fetch";

import { env } from "@/env";

import { ApiError, toApiError } from "./errors";
import { refreshAccessToken } from "./refresh";
import type { paths } from "./schema.gen";
import { useSession } from "./session";

/** 만료까지 이 시간보다 적게 남았으면 요청 전에 미리 갱신한다 (decisions F19). */
export const REFRESH_AHEAD_MS = 30_000;

function isAuthEndpoint(url: string): boolean {
  return new URL(url).pathname.startsWith("/api/v1/auth/");
}

async function ensureFreshToken(): Promise<void> {
  const { accessToken, expiresAt } = useSession.getState();
  if (!accessToken || expiresAt === null || expiresAt - Date.now() > REFRESH_AHEAD_MS) return;
  try {
    await refreshAccessToken();
  } catch {
    // 일시 오류면 지금 토큰으로 보내 보고, 401이면 아래에서 한 번 더 갱신한다
  }
}

function withToken(request: Request): Request {
  const token = useSession.getState().accessToken;
  if (token) request.headers.set("Authorization", `Bearer ${token}`);
  return request;
}

/** 401이면 다시 보내야 하므로 보내기 전 요청(본문 포함)을 복제해 둔다. */
const retryable = new Map<string, Request>();

const authMiddleware: Middleware = {
  async onRequest({ request, id }) {
    if (isAuthEndpoint(request.url)) return request; // 로그인·갱신·가입은 access 토큰을 쓰지 않는다
    await ensureFreshToken();
    const prepared = withToken(request);
    if (useSession.getState().accessToken) retryable.set(id, prepared.clone());
    return prepared;
  },
  async onResponse({ response, id, options }) {
    const original = retryable.get(id);
    retryable.delete(id);
    if (response.status !== 401 || !original) return response;
    // access 토큰이 만료·무효: 한 번 갱신하고 다시 보낸다 (다시 401이면 그대로 돌려준다)
    if (!(await refreshAccessToken().catch(() => false))) return response;
    return options.fetch(withToken(original));
  },
  onError({ id }) {
    retryable.delete(id);
  },
};

/**
 * 백엔드 API 클라이언트. 경로·요청·응답 타입은 OpenAPI에서 생성한 `schema.gen.ts`를 쓴다.
 * 예: `api.GET("/api/v1/me")`
 */
export const api = createClient<paths>({
  baseUrl: env.backendUrl,
  credentials: "include",
  // 테스트(MSW)가 바꾼 fetch를 쓰도록 호출할 때마다 전역 fetch를 찾는다
  fetch: (request) => globalThis.fetch(request),
});
api.use(authMiddleware);

/**
 * openapi-fetch 결과에서 데이터를 꺼내고, 오류면 ApiError를 던진다 (Query의 queryFn·mutationFn에서 쓴다).
 * 예: `queryFn: () => unwrap(api.GET("/api/v1/me"))`
 */
export async function unwrap<T>(result: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await result;
  if (!response.ok) throw toApiError(response.status, error, response.headers.get("Retry-After"));
  return data as T;
}

export { ApiError };
