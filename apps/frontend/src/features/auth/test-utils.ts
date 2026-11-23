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

/** 열어 둔 채 프레임만 보내는 SSE 응답 (테스트용). 끝나지 않으므로 연결은 화면이 닫을 때 끊긴다 */
export function sseResponse(frames: string[]): HttpResponse<ReadableStream> {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      for (const frame of frames) controller.enqueue(encoder.encode(frame));
    },
  });
  return new HttpResponse(body, { headers: { "Content-Type": "text/event-stream" } });
}

/** 테스트가 원하는 때 프레임을 보내는 SSE 연결 (연결마다 새 응답) */
export function pushableSse(): { respond: () => HttpResponse<ReadableStream>; push: (frame: string) => void } {
  const encoder = new TextEncoder();
  const controllers: ReadableStreamDefaultController<Uint8Array>[] = [];
  return {
    respond: () =>
      new HttpResponse(
        new ReadableStream<Uint8Array>({
          start(controller) {
            controllers.push(controller);
            controller.enqueue(encoder.encode("event: ready\ndata: {}\n\n"));
          },
        }),
        { headers: { "Content-Type": "text/event-stream" } },
      ),
    push: (frame) => {
      for (const c of controllers) {
        try {
          c.enqueue(encoder.encode(frame));
        } catch {
          // 이미 닫힌 연결
        }
      }
    },
  };
}

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
    // 공통 틀이 '내 팀' 메뉴를 정하려고 부른다 (F39). 기본은 팀 없음
    http.get(apiUrl("/api/v1/me/mentoring-teams"), () => HttpResponse.json({ as_student: [], as_mentor: [] })),
    // 공통 틀의 채팅 안 읽음 배지·실시간 수신 (F41). 기본은 방 없음, 연결은 열어 두기만 한다
    http.get(apiUrl("/api/v1/me/mentoring/chat/threads"), () =>
      HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
    ),
    http.get(apiUrl("/api/v1/me/mentoring/chat/stream"), () => sseResponse(["event: ready\ndata: {}\n\n"])),
    // 수강생 홈의 요약·멘토링 카드 (F42). 기본은 세션·신청·계좌 없음
    http.get(apiUrl("/api/v1/me/mentoring/sessions"), () => HttpResponse.json(emptyPage(SESSION_COUNTS))),
    http.get(apiUrl("/api/v1/me/mentoring/requests"), () => HttpResponse.json(emptyPage(REQUEST_COUNTS))),
    http.get(apiUrl("/api/v1/me/balances"), () => HttpResponse.json([])),
  );
}

const SESSION_COUNTS = { SCHEDULED: 0, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 };
const REQUEST_COUNTS = { PENDING: 0, APPROVED: 0, REJECTED: 0, CANCELED: 0 };

function emptyPage<C>(counts: C) {
  return { items: [], total: 0, limit: 20, offset: 0, counts };
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
