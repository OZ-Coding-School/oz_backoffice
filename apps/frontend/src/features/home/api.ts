import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { kstDateKey } from "@/features/apply/slots";

type SessionStatus = components["schemas"]["MentoringSessionStatus"];

/** 예정·진행 중 (F42: 오늘 멘토링·다가오는 세션) */
const UPCOMING: SessionStatus[] = ["SCHEDULED", "IN_PROGRESS"];

export const UPCOMING_LIMIT = 3;
export const PENDING_LIMIT = 2;

const DAY_MS = 24 * 60 * 60_000;

/** 오늘(KST) 00:00 ~ 내일 00:00. 한국은 일광 절약 시간이 없어 하루는 24시간이다 */
export function kstToday(now: number): { from: string; to: string } {
  const start = new Date(`${kstDateKey(new Date(now))}T00:00:00+09:00`).getTime();
  return { from: new Date(start).toISOString(), to: new Date(start + DAY_MS).toISOString() };
}

/** 오늘 KST 날짜인지 */
export function isKstToday(iso: string, now: number): boolean {
  return kstDateKey(iso) === kstDateKey(new Date(now));
}

// 키는 세션·신청 목록 아래에 두어 취소·변경 뒤 무효화에 함께 걸리게 한다
export const homeKeys = {
  today: (day: string) => ["sessions", "mine", "home-today", day] as const,
  upcoming: ["sessions", "mine", "home-upcoming"] as const,
  pending: ["requests", "mine", "home-pending"] as const,
};

/** 오늘 멘토링 수 (total만 쓴다) */
export function todaySessionsQuery(now: number) {
  const { from, to } = kstToday(now);
  return queryOptions({
    queryKey: homeKeys.today(from),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/me/mentoring/sessions", {
          params: { query: { status: UPCOMING, from, to, limit: 1, offset: 0 } },
        }),
      ),
  });
}

/** 다가오는 세션: 시작 시각 이른 순 3개 (A75) */
export const upcomingSessionsQuery = queryOptions({
  queryKey: homeKeys.upcoming,
  queryFn: () =>
    unwrap(
      api.GET("/api/v1/me/mentoring/sessions", {
        params: { query: { status: UPCOMING, order: "asc", limit: UPCOMING_LIMIT, offset: 0 } },
      }),
    ),
});

/** 승인 대기 신청 2개와 전체 수(total) */
export const pendingRequestsQuery = queryOptions({
  queryKey: homeKeys.pending,
  queryFn: () =>
    unwrap(
      api.GET("/api/v1/me/mentoring/requests", {
        params: { query: { status: ["PENDING"], limit: PENDING_LIMIT, offset: 0 } },
      }),
    ),
});
