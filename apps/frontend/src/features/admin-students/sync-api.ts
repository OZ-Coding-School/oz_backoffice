import { infiniteQueryOptions, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type SyncRun = components["schemas"]["RosterSyncRunResponse"];
export type SyncTarget = { scope: "ALL" } | { scope: "BOOTCAMP"; id: string } | { scope: "COHORT"; id: string };

export const syncKeys = {
  all: ["roster-sync"] as const,
  runs: () => ["roster-sync", "runs"] as const,
  run: (id: string) => ["roster-sync", "run", id] as const,
  unmapped: () => ["roster-sync", "unmapped"] as const,
};

export const RUNS_PAGE = 10;

/** 실행 이력 (최근부터, 커서 `before`). 담당 범위의 실행만 보인다 */
export const syncRunsQuery = infiniteQueryOptions({
  queryKey: syncKeys.runs(),
  initialPageParam: undefined as string | undefined,
  queryFn: ({ pageParam }) =>
    unwrap(
      api.GET("/api/v1/admin/rosters/sync-runs", {
        params: { query: { limit: RUNS_PAGE, ...(pageParam ? { before: pageParam } : {}) } },
      }),
    ),
  getNextPageParam: (last) => last.next_before ?? undefined,
});

/** 실행 하나 (진행 중이면 3초마다 다시 읽는다, F78) */
export function syncRunQuery(id: string) {
  return queryOptions({
    queryKey: syncKeys.run(id),
    queryFn: () => unwrap(api.GET("/api/v1/admin/rosters/sync-runs/{run_id}", { params: { path: { run_id: id } } })),
  });
}

/** 가장 최근에 성공한 전체 동기화의 매핑 실패 레코드 (전체 범위 조회 권한) */
export const unmappedQuery = queryOptions({
  queryKey: syncKeys.unmapped(),
  queryFn: () => unwrap(api.GET("/api/v1/admin/rosters/unmapped")),
});

/** 지금 실행 (202). 이미 진행 중이면 409 */
export function useStartSync() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (target: SyncTarget) =>
      target.scope === "ALL"
        ? unwrap(api.POST("/api/v1/admin/rosters/sync"))
        : target.scope === "BOOTCAMP"
          ? unwrap(
              api.POST("/api/v1/admin/bootcamps/{bootcamp_id}/rosters/sync", {
                params: { path: { bootcamp_id: target.id } },
              }),
            )
          : unwrap(
              api.POST("/api/v1/admin/cohorts/{cohort_id}/rosters/sync", {
                params: { path: { cohort_id: target.id } },
              }),
            ),
    onSuccess: () => client.invalidateQueries({ queryKey: syncKeys.runs() }),
  });
}
