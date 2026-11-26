import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { academyKeys } from "@/features/admin-academy/api";

export type MentoringSettings = components["schemas"]["SettingsResponse"];
export type SettingsBody = components["schemas"]["SettingsFields"];
export type BlockTime = components["schemas"]["BlockTimeResponse"];
export type BlockTimeBody = components["schemas"]["BlockTimeFields"];

export const mentoringSettingsKeys = {
  blockTimes: (cohortId: string) => ["admin-mentoring", "block-times", cohortId] as const,
};

/** 기수 금지 시간대 (A34) */
export function blockTimesQuery(cohortId: string) {
  return queryOptions({
    queryKey: mentoringSettingsKeys.blockTimes(cohortId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/cohorts/{cohort_id}/mentoring-block-times", {
          params: { path: { cohort_id: cohortId } },
        }),
      ),
  });
}

/** 설정 전체 저장(없으면 생성). 진행 중인 신청에는 소급하지 않는다 (A34) */
export function useSaveSettings(cohortId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: SettingsBody) =>
      unwrap(
        api.PUT("/api/v1/admin/cohorts/{cohort_id}/mentoring-settings", {
          params: { path: { cohort_id: cohortId } },
          body,
        }),
      ),
    onSuccess: (saved) => client.setQueryData(academyKeys.settings(cohortId), saved),
  });
}

/** 금지 시간대 추가(id 없음)·수정 */
export function useSaveBlockTime(cohortId: string, blockId: string | null) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: BlockTimeBody) =>
      blockId
        ? unwrap(
            api.PATCH("/api/v1/admin/cohorts/{cohort_id}/mentoring-block-times/{block_id}", {
              params: { path: { cohort_id: cohortId, block_id: blockId } },
              body,
            }),
          )
        : unwrap(
            api.POST("/api/v1/admin/cohorts/{cohort_id}/mentoring-block-times", {
              params: { path: { cohort_id: cohortId } },
              body,
            }),
          ),
    onSuccess: () => client.invalidateQueries({ queryKey: mentoringSettingsKeys.blockTimes(cohortId) }),
  });
}

export function useDeleteBlockTime(cohortId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (blockId: string) =>
      unwrap(
        api.DELETE("/api/v1/admin/cohorts/{cohort_id}/mentoring-block-times/{block_id}", {
          params: { path: { cohort_id: cohortId, block_id: blockId } },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: mentoringSettingsKeys.blockTimes(cohortId) }),
  });
}
