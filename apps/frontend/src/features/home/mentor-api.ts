import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { MentoringRequest } from "@/features/requests/api";
import { formatKst, formatKstDay } from "@/lib/datetime";

import { kstToday } from "./api";

/** 멘토 홈 목록 카드에 보이는 수 (F57) */
export const MENTOR_HOME_LIMIT = 3;

// 키는 멘토 세션·받은 신청 키 아래에 두어 승인·기록·취소 뒤 함께 다시 부른다
export const mentorHomeKeys = {
  today: (day: string) => ["sessions", "mentor", "home-today", day] as const,
  upcoming: ["sessions", "mentor", "home-upcoming"] as const,
  missing: ["sessions", "mentor", "home-record-missing"] as const,
  pending: ["mentor-requests", "home-pending"] as const,
};

/** 오늘 세션 수: 오늘(KST) 예정·진행 중 (total만 쓴다) */
export function mentorTodayQuery(now: number) {
  const { from, to } = kstToday(now);
  return queryOptions({
    queryKey: mentorHomeKeys.today(from),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/me/mentor-sessions", {
          params: { query: { status: ["SCHEDULED", "IN_PROGRESS"], from, to, limit: 1, offset: 0 } },
        }),
      ),
  });
}

/** 다가오는 세션 3개(이른 순)와 탭 건수(기록 미제출 수, A77) */
export const mentorUpcomingQuery = queryOptions({
  queryKey: mentorHomeKeys.upcoming,
  queryFn: () =>
    unwrap(
      api.GET("/api/v1/me/mentor-sessions", {
        params: { query: { view: "upcoming", order: "asc", limit: MENTOR_HOME_LIMIT, offset: 0 } },
      }),
    ),
});

/** 기록 미제출 중 가장 오래된 하나 (경고 상자) */
export const mentorOldestMissingQuery = queryOptions({
  queryKey: mentorHomeKeys.missing,
  queryFn: () =>
    unwrap(
      api.GET("/api/v1/me/mentor-sessions", {
        params: { query: { view: "record_missing", order: "asc", limit: 1, offset: 0 } },
      }),
    ),
});

/** 처리할 신청: 대기 3개와 대기 수 */
export const mentorPendingQuery = queryOptions({
  queryKey: mentorHomeKeys.pending,
  queryFn: () =>
    unwrap(
      api.GET("/api/v1/me/mentor-requests", {
        params: { query: { status: ["PENDING"], limit: MENTOR_HOME_LIMIT, offset: 0 } },
      }),
    ),
});

/** "희망 3개 · 가장 이른 11/24(화) 19:00" (신청 응답에 마감이 없어 가장 이른 희망을 보여 준다, F57) */
export function desiredSummary(request: Pick<MentoringRequest, "desired_times">): string {
  const [first] = [...request.desired_times].sort();
  const count = `희망 ${request.desired_times.length}개`;
  return first ? `${count} · 가장 이른 ${formatKstDay(first)} ${formatKst(first, "HH:mm")}` : count;
}
