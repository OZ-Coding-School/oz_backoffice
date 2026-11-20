import { infiniteQueryOptions, queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type MentoringSession = components["schemas"]["SessionResponse"];
export type SessionStatus = components["schemas"]["MentoringSessionStatus"];
export type SessionCounts = components["schemas"]["SessionStatusCounts"];

export const PAGE_SIZE = 20;

/** 목록 탭 (F33·A70): 예정 탭은 예정과 진행 중을 함께 보여 준다 */
export const SESSION_TABS = [
  { value: "all", label: "전체", statuses: [] },
  { value: "scheduled", label: "예정", statuses: ["SCHEDULED", "IN_PROGRESS"] },
  { value: "completed", label: "완료", statuses: ["COMPLETED"] },
  { value: "canceled", label: "취소", statuses: ["CANCELED"] },
  { value: "no_show", label: "노쇼", statuses: ["NO_SHOW"] },
] as const satisfies readonly { value: string; label: string; statuses: readonly SessionStatus[] }[];

export type SessionTab = (typeof SESSION_TABS)[number]["value"];

const ALL_STATUSES: readonly SessionStatus[] = ["SCHEDULED", "IN_PROGRESS", "COMPLETED", "NO_SHOW", "CANCELED"];

/** 탭 건수: counts는 필터와 무관한 전체 기준이다 (A68) */
export function tabCount(tab: SessionTab, counts: SessionCounts): number {
  const def = SESSION_TABS.find((t) => t.value === tab);
  const statuses: readonly SessionStatus[] = def?.statuses.length ? def.statuses : ALL_STATUSES;
  return statuses.reduce((sum, s) => sum + counts[s], 0);
}

export function isSessionTab(value: unknown): value is SessionTab {
  return SESSION_TABS.some((t) => t.value === value);
}

export const sessionKeys = {
  all: ["sessions"] as const,
  list: (tab: SessionTab) => ["sessions", "mine", tab] as const,
  detail: (id: string) => ["sessions", "detail", id] as const,
};

/** 내 세션 목록 (본인 1:1 + 소속 팀, 20개씩 이어 붙인다, F33) */
export function mySessionsQuery(tab: SessionTab) {
  const statuses = [...(SESSION_TABS.find((t) => t.value === tab)?.statuses ?? [])];
  return infiniteQueryOptions({
    queryKey: sessionKeys.list(tab),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/me/mentoring/sessions", {
          params: {
            query: { limit: PAGE_SIZE, offset: pageParam, ...(statuses.length ? { status: statuses } : {}) },
          },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
  });
}

/** 세션 단건 (참여자·담당 멘토만, 아니면 404) */
export function sessionQuery(id: string) {
  return queryOptions({
    queryKey: sessionKeys.detail(id),
    queryFn: () => unwrap(api.GET("/api/v1/mentoring/sessions/{session_id}", { params: { path: { session_id: id } } })),
  });
}
