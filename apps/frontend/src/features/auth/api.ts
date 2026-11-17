import { queryOptions, type QueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import { ApiError } from "@/api/errors";
import { refreshAccessToken } from "@/api/refresh";
import type { components } from "@/api/schema.gen";
import { endSession, hasSession, setAccessToken } from "@/api/session";

export type Me = components["schemas"]["MeResponse"];
export type MemberSignup = components["schemas"]["MemberSignupResponse"];
export type SignupCohort = components["schemas"]["SignupCohortResponse"];
export type ResubmitRequest = components["schemas"]["ResubmitRequest"];

export const authKeys = {
  me: ["auth", "me"] as const,
  memberSignup: ["auth", "member-signup"] as const,
  signupCohorts: ["auth", "signup-cohorts"] as const,
};

export const meQuery = queryOptions({
  queryKey: authKeys.me,
  queryFn: () => unwrap(api.GET("/api/v1/me")),
  staleTime: 60_000,
});

export const memberSignupQuery = queryOptions({
  queryKey: authKeys.memberSignup,
  queryFn: () => unwrap(api.GET("/api/v1/me/member-signup")),
});

export const signupCohortsQuery = queryOptions({
  queryKey: authKeys.signupCohorts,
  queryFn: () => unwrap(api.GET("/api/v1/auth/signup/cohorts")),
  staleTime: 5 * 60_000,
});

let restored: Promise<void> | null = null;

/**
 * 앱을 연 뒤 처음 한 번 refresh 쿠키로 세션을 되살리고(`/auth/refresh`), 로그인 사용자를 돌려준다.
 * 세션이 없으면 null. 라우트 가드(`beforeLoad`)가 부른다.
 */
export async function ensureSession(queryClient: QueryClient): Promise<Me | null> {
  if (!hasSession()) {
    restored ??= refreshAccessToken()
      .then(() => undefined)
      .catch(() => undefined); // 네트워크 오류면 비로그인으로 본다 (다음 이동 때 다시 시도하지 않음)
    await restored;
  }
  if (!hasSession()) return null;
  try {
    return await queryClient.ensureQueryData(meQuery);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

/** 테스트용: 앱 시작 복원을 다시 하게 한다. */
export function resetSessionRestoreForTest(): void {
  restored = null;
}

/** 로그인. 성공하면 access 토큰을 세션에 두고 사용자 정보를 새로 불러온다. */
export async function login(queryClient: QueryClient, body: { email: string; password: string }): Promise<Me> {
  const token = await unwrap(api.POST("/api/v1/auth/login", { body }));
  setAccessToken(token.access_token, token.expires_at);
  queryClient.removeQueries({ queryKey: ["auth"] });
  return queryClient.fetchQuery(meQuery);
}

/** 로그아웃. 서버 세션(refresh)을 지우고 이 탭의 세션·캐시를 비운다. 안내 문구는 띄우지 않는다. */
export async function logout(): Promise<void> {
  await api.POST("/api/v1/auth/logout").catch(() => undefined);
  endSession(LOGGED_OUT, { broadcast: false });
}

export const LOGGED_OUT = "logged_out";
