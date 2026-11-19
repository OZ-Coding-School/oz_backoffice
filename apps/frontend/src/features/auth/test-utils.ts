import { http, HttpResponse } from "msw";

import { resetSessionForTest } from "@/api/session";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";

import { resetSessionRestoreForTest, type Me, type MemberSignup } from "./api";

export function makeMe(overrides: Partial<Me> = {}): Me {
  return {
    id: "u1",
    email: "student@gmail.com",
    name: "가수강",
    account_type: "STUDENT",
    phone_number: "01012345678",
    approval_status: "APPROVED",
    approved_at: "2026-11-16T01:00:00Z",
    roles: [{ role: "STUDENT", scope_type: "COHORT", scope_id: "c1", expires_at: null }],
    ...overrides,
  };
}

export function makeSignup(overrides: Partial<MemberSignup> = {}): MemberSignup {
  return {
    id: "s1",
    signup_type: "STUDENT",
    status: "PENDING",
    requested_cohort_id: "c12",
    nickname: null,
    display_name_preference: null,
    match_result: "NO_MATCH",
    reject_reason: null,
    reviewed_at: null,
    created_at: "2026-11-16T01:00:00Z",
    ...overrides,
  };
}

export const COHORTS = [
  {
    cohort_id: "c12",
    bootcamp_id: "b1",
    bootcamp_name: "백엔드",
    cohort_number: 12,
    start_date: "2026-10-01",
    end_date: "2027-03-31",
  },
  {
    cohort_id: "c13",
    bootcamp_id: "b1",
    bootcamp_name: "백엔드",
    cohort_number: 13,
    start_date: "2026-12-01",
    end_date: "2027-05-31",
  },
];

/** 수강 중 기수 하나 (A64·F27) */
export const ENROLLMENTS = [
  {
    student_id: "st12",
    cohort_id: "c12",
    bootcamp_id: "b1",
    bootcamp_name: "초격차 백엔드",
    cohort_number: 12,
    cohort_status: "ONGOING" as const,
    start_date: "2026-10-01",
    end_date: "2027-03-31",
    status: "ENROLLED" as const,
    enrolled_at: "2026-10-01",
    ended_at: null,
  },
];

/** 기수 멘토링 설정 요약 (A64). 기본은 1:1·팀 모두 허용이라 FE-3a의 '멘토링 신청' 메뉴가 없다 (F30) */
export const MENTORING_SETTINGS = {
  cohort_id: "c12",
  allow_1_on_1: true,
  allow_team_mentoring: true,
  allowed_duration: 60,
  min_lead_hours: 24,
  max_pending_requests: 3,
};

/** 세션·복원 상태를 비우고, 기본으로 refresh 쿠키가 없는 상태를 모킹한다. */
export function resetAuth(): void {
  resetSessionForTest();
  resetSessionRestoreForTest();
  server.use(
    http.post(apiUrl("/api/v1/auth/refresh"), () =>
      HttpResponse.json(errorBody("refresh_token_missing"), { status: 401 }),
    ),
    http.post(apiUrl("/api/v1/auth/logout"), () => new HttpResponse(null, { status: 204 })),
    http.get(apiUrl("/api/v1/auth/signup/cohorts"), () => HttpResponse.json(COHORTS)),
    http.get(apiUrl("/api/v1/me/enrollments"), () => HttpResponse.json(ENROLLMENTS)),
    http.get(apiUrl("/api/v1/me/mentoring/settings"), () => HttpResponse.json(MENTORING_SETTINGS)),
  );
}

/** refresh 쿠키가 살아 있고 /me가 이 사용자인 상태 (앱을 새로 열었을 때). */
export function mockSignedIn(me: Me): void {
  server.use(
    http.post(apiUrl("/api/v1/auth/refresh"), () =>
      HttpResponse.json({ access_token: "token", expires_at: new Date(Date.now() + 15 * 60_000).toISOString() }),
    ),
    http.get(apiUrl("/api/v1/me"), () => HttpResponse.json(me)),
  );
}

/** 로그인 API가 성공하고 /me가 이 사용자를 돌려준다. */
export function mockLogin(me: Me): void {
  server.use(
    http.post(apiUrl("/api/v1/auth/login"), () =>
      HttpResponse.json({ access_token: "token", expires_at: new Date(Date.now() + 15 * 60_000).toISOString() }),
    ),
    http.get(apiUrl("/api/v1/me"), () => HttpResponse.json(me)),
  );
}
