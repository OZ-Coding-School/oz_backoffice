import { infiniteQueryOptions, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { requestKeys, type RequestCounts, type RequestStatus } from "@/features/requests/api";

export type MyAssignment = components["schemas"]["MyAssignmentResponse"];

export const PAGE_SIZE = 20;

/** 목록 탭 (Figma `받은 신청`, F43): 대기가 기본이고 전체는 맨 뒤 */
export const RECEIVED_TABS = [
  { value: "pending", label: "대기", statuses: ["PENDING"] },
  { value: "approved", label: "승인", statuses: ["APPROVED"] },
  { value: "rejected", label: "반려", statuses: ["REJECTED"] },
  { value: "canceled", label: "취소", statuses: ["CANCELED"] },
  { value: "all", label: "전체", statuses: [] },
] as const satisfies readonly { value: string; label: string; statuses: readonly RequestStatus[] }[];

export type ReceivedTab = (typeof RECEIVED_TABS)[number]["value"];

export function isReceivedTab(value: unknown): value is ReceivedTab {
  return RECEIVED_TABS.some((t) => t.value === value);
}

/** 탭 건수: counts는 상태 필터와 무관하고 기수 필터는 따른다 (A76) */
export function receivedTabCount(tab: ReceivedTab, counts: RequestCounts): number {
  const def = RECEIVED_TABS.find((t) => t.value === tab);
  const statuses: readonly RequestStatus[] = def?.statuses.length
    ? def.statuses
    : ["PENDING", "APPROVED", "REJECTED", "CANCELED"];
  return statuses.reduce((sum, s) => sum + counts[s], 0);
}

export const receivedKeys = {
  all: ["mentor-requests"] as const,
  list: (tab: ReceivedTab, cohortId: string | undefined) =>
    ["mentor-requests", "list", tab, cohortId ?? "all"] as const,
  pending: ["mentor-requests", "pending-count"] as const,
  assignments: ["mentor-requests", "assignments"] as const,
};

/** 받은 신청 (20개씩 이어 붙인다, 기수 필터 A76) */
export function receivedRequestsQuery(tab: ReceivedTab, cohortId: string | undefined) {
  const statuses = [...(RECEIVED_TABS.find((t) => t.value === tab)?.statuses ?? [])];
  return infiniteQueryOptions({
    queryKey: receivedKeys.list(tab, cohortId),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/me/mentor-requests", {
          params: {
            query: {
              limit: PAGE_SIZE,
              offset: pageParam,
              ...(statuses.length ? { status: statuses } : {}),
              ...(cohortId ? { cohort_id: cohortId } : {}),
            },
          },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
  });
}

/** 메뉴 배지: 전체 기수의 승인 대기 건수 (F44) */
export const pendingCountQuery = queryOptions({
  queryKey: receivedKeys.pending,
  queryFn: () =>
    unwrap(api.GET("/api/v1/me/mentor-requests", { params: { query: { status: ["PENDING"], limit: 1, offset: 0 } } })),
  select: (page) => page.counts.PENDING,
});

/** 기수 필터 보기: 내 배정 기수 전체 (비활성 포함, F43) */
export const myAssignmentsQuery = queryOptions({
  queryKey: receivedKeys.assignments,
  queryFn: () => unwrap(api.GET("/api/v1/me/mentor-assignments", { params: { query: { include_inactive: true } } })),
  staleTime: 5 * 60_000,
});

/** 배정 → 기수 보기 (같은 기수는 하나, 최근 시작 순) */
export function cohortOptions(assignments: readonly MyAssignment[]): { id: string; label: string }[] {
  const byCohort = new Map<string, MyAssignment>();
  for (const a of [...assignments].sort((x, y) => y.start_date.localeCompare(x.start_date))) {
    if (!byCohort.has(a.cohort_id)) byCohort.set(a.cohort_id, a);
  }
  return [...byCohort.values()].map((a) => ({ id: a.cohort_id, label: `${a.bootcamp_name} ${a.cohort_number}기` }));
}

/** 승인 (A43): 희망 일시 하나로 세션을 만든다. 응답의 신청으로 상세 캐시를 고치고 목록·배지·세션을 새로 부른다 */
export function useApproveRequest(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (startsAt: string) =>
      unwrap(
        api.POST("/api/v1/mentoring/requests/{request_id}/approve", {
          params: { path: { request_id: id } },
          body: { starts_at: startsAt },
        }),
      ),
    onSuccess: ({ request }) => {
      queryClient.setQueryData(requestKeys.detail(id), request);
      void queryClient.invalidateQueries({ queryKey: receivedKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

/** 반려 (A42): 사유 필수 300자. 신청자의 차감 예정 시간이 돌아간다 */
export function useRejectRequest(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) =>
      unwrap(
        api.POST("/api/v1/mentoring/requests/{request_id}/reject", {
          params: { path: { request_id: id } },
          body: { reason },
        }),
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData(requestKeys.detail(id), updated);
      void queryClient.invalidateQueries({ queryKey: receivedKeys.all });
    },
  });
}
