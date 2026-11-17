import { env } from "@/env";

import { readApiError } from "./errors";
import { endSession, hasSession, setAccessToken } from "./session";

/** 탭 간 갱신 잠금 이름. 같은 사이트의 모든 탭이 공유한다 (decisions F19). */
export const REFRESH_LOCK = "oz-auth-refresh";

let inFlight: Promise<boolean> | null = null;

/**
 * refresh 쿠키로 access 토큰을 새로 받는다.
 * - 이 탭 안의 동시 요청은 갱신 하나를 같이 기다린다.
 * - 탭끼리는 Web Locks로 한 번에 한 탭만 갱신한다. 기다린 탭은 앞 탭이 회전한 새 쿠키로 요청하므로
 *   같은 refresh를 두 번 보내 재사용으로 판정되지 않는다 (백엔드 유예 시간 A60과 함께).
 *
 * @returns 갱신했으면 true, 세션이 끝났으면(401) false. 네트워크·서버 오류는 던진다(세션은 유지).
 */
export function refreshAccessToken(): Promise<boolean> {
  inFlight ??= withRefreshLock(requestRefresh).finally(() => {
    inFlight = null;
  });
  return inFlight;
}

function withRefreshLock(task: () => Promise<boolean>): Promise<boolean> {
  const locks = typeof navigator === "undefined" ? undefined : navigator.locks;
  // Web Locks를 지원하지 않는 환경(일부 테스트 환경 등)에서는 탭 안에서만 하나로 모은다
  return locks ? locks.request(REFRESH_LOCK, task) : task();
}

async function requestRefresh(): Promise<boolean> {
  const response = await fetch(`${env.apiBaseUrl}/auth/refresh`, { method: "POST", credentials: "include" });
  if (response.ok) {
    const body = (await response.json()) as { access_token: string; expires_at: string };
    setAccessToken(body.access_token, body.expires_at);
    return true;
  }
  const error = await readApiError(response);
  if (response.status === 401) {
    // 끝낼 세션이 있을 때만 끝낸다. 처음 방문(쿠키 없음)이 앞서 남은 종료 사유를 덮지 않게 한다
    if (hasSession()) endSession(error.code);
    return false;
  }
  throw error;
}
