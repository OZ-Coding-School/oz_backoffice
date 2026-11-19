import { infiniteQueryOptions, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type MentoringRequest = components["schemas"]["RequestResponse"];
export type RequestStatus = components["schemas"]["MentoringRequestStatus"];
export type RequestCounts = components["schemas"]["RequestStatusCounts"];
export type BalanceAccount = components["schemas"]["AccountResponse"];

export const PAGE_SIZE = 20;

/** 목록 탭 (F29·A67): 반려·취소는 한 탭으로 묶어 상태 두 개를 보낸다 */
export const REQUEST_TABS = [
  { value: "all", label: "전체", statuses: [] },
  { value: "pending", label: "승인 대기", statuses: ["PENDING"] },
  { value: "approved", label: "승인", statuses: ["APPROVED"] },
  { value: "closed", label: "반려·취소", statuses: ["REJECTED", "CANCELED"] },
] as const satisfies readonly { value: string; label: string; statuses: readonly RequestStatus[] }[];

export type RequestTab = (typeof REQUEST_TABS)[number]["value"];

const ALL_STATUSES: readonly RequestStatus[] = ["PENDING", "APPROVED", "REJECTED", "CANCELED"];

/** 탭 건수: counts는 필터와 무관한 전체 기준이다 (A67) */
export function tabCount(tab: RequestTab, counts: RequestCounts): number {
  const def = REQUEST_TABS.find((t) => t.value === tab);
  const statuses: readonly RequestStatus[] = def?.statuses.length ? def.statuses : ALL_STATUSES;
  return statuses.reduce((sum, s) => sum + counts[s], 0);
}

export function isRequestTab(value: unknown): value is RequestTab {
  return REQUEST_TABS.some((t) => t.value === value);
}

export const requestKeys = {
  all: ["requests"] as const,
  list: (tab: RequestTab) => ["requests", "mine", tab] as const,
  detail: (id: string) => ["requests", "detail", id] as const,
  balances: ["member", "balances"] as const,
  settings: (cohortId: string) => ["member", "mentoring-settings", cohortId] as const,
};

/** 내 신청 목록 (본인 1:1 + 소속 팀, 20개씩 이어 붙인다, F29) */
export function myRequestsQuery(tab: RequestTab) {
  const statuses = [...(REQUEST_TABS.find((t) => t.value === tab)?.statuses ?? [])];
  return infiniteQueryOptions({
    queryKey: requestKeys.list(tab),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/me/mentoring/requests", {
          params: {
            query: { limit: PAGE_SIZE, offset: pageParam, ...(statuses.length ? { status: statuses } : {}) },
          },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
  });
}

/** 신청 단건 (신청자·팀원·담당 멘토만, A66) */
export function requestQuery(id: string) {
  return queryOptions({
    queryKey: requestKeys.detail(id),
    queryFn: () => unwrap(api.GET("/api/v1/mentoring/requests/{request_id}", { params: { path: { request_id: id } } })),
  });
}

/** 내 시간 계좌 (1:1 + 소속 팀) */
export const balancesQuery = queryOptions({
  queryKey: requestKeys.balances,
  queryFn: () => unwrap(api.GET("/api/v1/me/balances")),
});

/** 기수 멘토링 설정 요약 (취소 마감 min_lead_hours, A64). 수강 중 수강생만 볼 수 있다 */
export function mentoringSettingsQuery(cohortId: string) {
  return queryOptions({
    queryKey: requestKeys.settings(cohortId),
    queryFn: () => unwrap(api.GET("/api/v1/me/mentoring/settings", { params: { query: { cohort_id: cohortId } } })),
    staleTime: 5 * 60_000,
  });
}

export function useCancelRequest(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) =>
      unwrap(
        api.POST("/api/v1/mentoring/requests/{request_id}/cancel", {
          params: { path: { request_id: id } },
          body: { reason },
        }),
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData(requestKeys.detail(id), updated);
      void queryClient.invalidateQueries({ queryKey: ["requests", "mine"] });
      void queryClient.invalidateQueries({ queryKey: requestKeys.balances });
    },
  });
}
