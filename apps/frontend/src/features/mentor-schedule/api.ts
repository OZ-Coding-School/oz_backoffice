import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

import { dayStartMs, addDays } from "./schedule";

export const scheduleKeys = {
  mine: ["mentor-schedule"] as const,
  // 세션 목록 키 아래에 두어 기록·취소 뒤 함께 다시 부른다
  weekSessions: (monday: string) => ["sessions", "mentor", "week", monday] as const,
  /** 운영진 일정 대리 (F85·A106) */
  of: (mentorId: string) => ["mentor-schedule", "admin", mentorId] as const,
  weekSessionsOf: (mentorId: string, monday: string) => ["sessions", "admin-mentor", mentorId, "week", monday] as const,
};

/** 내 일정: 신청 받기 + 끝나지 않은 불가 시간 (F52) */
export const scheduleQuery = queryOptions({
  queryKey: scheduleKeys.mine,
  queryFn: () => unwrap(api.GET("/api/v1/me/mentor-schedule")),
});

/** 대상 멘토의 일정: mentorId가 없으면 내 일정 (운영진 일정 대리 F85) */
export function scheduleQueryOf(mentorId: string | null) {
  return queryOptions({
    queryKey: (mentorId ? scheduleKeys.of(mentorId) : scheduleKeys.mine) as readonly string[],
    queryFn: () =>
      mentorId
        ? unwrap(api.GET("/api/v1/admin/mentors/{mentor_id}/schedule", { params: { path: { mentor_id: mentorId } } }))
        : unwrap(api.GET("/api/v1/me/mentor-schedule")),
  });
}

/** 대상 멘토의 그 주 세션 (운영진은 A106). 시간표에는 목록만 쓴다 */
export function weekSessionsQueryOf(monday: string, mentorId: string | null) {
  const from = new Date(dayStartMs(monday)).toISOString();
  const to = new Date(dayStartMs(addDays(monday, 7))).toISOString();
  const query = { from, to, status: WEEK_STATUSES, order: "asc" as const, limit: 100, offset: 0 };
  return queryOptions({
    queryKey: (mentorId
      ? scheduleKeys.weekSessionsOf(mentorId, monday)
      : scheduleKeys.weekSessions(monday)) as readonly string[],
    queryFn: async () => ({
      items: (mentorId
        ? await unwrap(
            api.GET("/api/v1/admin/mentors/{mentor_id}/sessions", { params: { path: { mentor_id: mentorId }, query } }),
          )
        : await unwrap(api.GET("/api/v1/me/mentor-sessions", { params: { query } }))
      ).items,
    }),
  });
}

const WEEK_STATUSES: ("SCHEDULED" | "IN_PROGRESS" | "COMPLETED" | "NO_SHOW")[] = [
  "SCHEDULED",
  "IN_PROGRESS",
  "COMPLETED",
  "NO_SHOW",
];

/** 그 주(월 00:00 ~ 다음 월 00:00 KST)의 내 세션. 취소는 뺀다 */
export function weekSessionsQuery(monday: string) {
  const from = new Date(dayStartMs(monday)).toISOString();
  const to = new Date(dayStartMs(addDays(monday, 7))).toISOString();
  return queryOptions({
    queryKey: scheduleKeys.weekSessions(monday),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/me/mentor-sessions", {
          params: {
            query: {
              from,
              to,
              status: WEEK_STATUSES,
              order: "asc",
              limit: 100,
              offset: 0,
            },
          },
        }),
      ),
  });
}

/** 신청 받기 (A37·A45): 끄면 대기 신청이 자동 취소되고 건수가 온다 */
export function useSetAccepting(mentorId: string | null = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (accepting: boolean) =>
      mentorId
        ? unwrap(
            api.PUT("/api/v1/admin/mentors/{mentor_id}/schedule/accepting", {
              params: { path: { mentor_id: mentorId } },
              body: { accepting_requests: accepting },
            }),
          )
        : unwrap(api.PUT("/api/v1/me/mentor-schedule/accepting", { body: { accepting_requests: accepting } })),
    onSuccess: (result) => {
      if (mentorId) void queryClient.invalidateQueries({ queryKey: ["admin-mentors"] });
      queryClient.setQueryData(mentorId ? scheduleKeys.of(mentorId) : scheduleKeys.mine, (prev) =>
        prev ? { ...prev, accepting_requests: result.accepting_requests } : prev,
      );
      if (result.canceled_pending_requests > 0) void queryClient.invalidateQueries({ queryKey: ["mentor-requests"] });
    },
  });
}

export type UnavailableInput = components["schemas"]["UnavailableInput"];
export type ScheduleChange = components["schemas"]["ChangeResponse"];

/** 등록·수정 뒤: 일정과(충돌을 정리했으면) 세션·받은 신청 목록을 다시 부른다 */
function useAfterChange(mentorId: string | null) {
  const queryClient = useQueryClient();
  return (change: ScheduleChange) => {
    if (!change.applied) return;
    void queryClient.invalidateQueries({ queryKey: mentorId ? scheduleKeys.of(mentorId) : scheduleKeys.mine });
    if (change.conflicts.length > 0) {
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
      void queryClient.invalidateQueries({ queryKey: ["mentor-requests"] });
    }
  };
}

/**
 * 불가 시간 저장 (A37·F53). 충돌이 있으면 `applied=false`와 충돌 목록이 오고,
 * `confirm=true`로 다시 보내면 저장하면서 대기 신청은 반려, 세션은 취소·환불한다.
 */
export function useSaveUnavailable(periodId: string | null, mentorId: string | null = null) {
  const after = useAfterChange(mentorId);
  return useMutation({
    mutationFn: ({ body, confirm }: { body: UnavailableInput; confirm: boolean }) =>
      mentorId
        ? periodId
          ? unwrap(
              api.PUT("/api/v1/admin/mentors/{mentor_id}/schedule/unavailable-periods/{period_id}", {
                params: { path: { mentor_id: mentorId, period_id: periodId }, query: { confirm } },
                body,
              }),
            )
          : unwrap(
              api.POST("/api/v1/admin/mentors/{mentor_id}/schedule/unavailable-periods", {
                params: { path: { mentor_id: mentorId }, query: { confirm } },
                body,
              }),
            )
        : periodId
          ? unwrap(
              api.PUT("/api/v1/me/mentor-schedule/unavailable-periods/{period_id}", {
                params: { path: { period_id: periodId }, query: { confirm } },
                body,
              }),
            )
          : unwrap(
              api.POST("/api/v1/me/mentor-schedule/unavailable-periods", { params: { query: { confirm } }, body }),
            ),
    onSuccess: after,
  });
}

export function useDeleteUnavailable(mentorId: string | null = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (periodId: string) =>
      mentorId
        ? unwrap(
            api.DELETE("/api/v1/admin/mentors/{mentor_id}/schedule/unavailable-periods/{period_id}", {
              params: { path: { mentor_id: mentorId, period_id: periodId } },
            }),
          )
        : unwrap(
            api.DELETE("/api/v1/me/mentor-schedule/unavailable-periods/{period_id}", {
              params: { path: { period_id: periodId } },
            }),
          ),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: mentorId ? scheduleKeys.of(mentorId) : scheduleKeys.mine }),
  });
}
