import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { orgKeys } from "@/features/admin-org/api";

export type Bootcamp = components["schemas"]["BootcampResponse"];
export type Cohort = components["schemas"]["CohortResponse"];
export type CohortStatus = Cohort["status"];
export type CohortSummary = components["schemas"]["CohortSummaryResponse"];
export type MentoringSettings = components["schemas"]["SettingsResponse"];

export const academyKeys = {
  all: ["admin-academy"] as const,
  bootcamps: () => ["admin-academy", "bootcamps"] as const,
  cohorts: (bootcampId: string) => ["admin-academy", "cohorts", bootcampId] as const,
  cohort: (id: string) => ["admin-academy", "cohort", id] as const,
  summary: (id: string) => ["admin-academy", "summary", id] as const,
  settings: (id: string) => ["admin-academy", "settings", id] as const,
};

/** 과정 전체 (사용 안 함 포함, 이름순) */
export const bootcampsQuery = queryOptions({
  queryKey: academyKeys.bootcamps(),
  queryFn: () => unwrap(api.GET("/api/v1/admin/bootcamps", { params: { query: { include_inactive: true } } })),
});

export function cohortsQuery(bootcampId: string) {
  return queryOptions({
    queryKey: academyKeys.cohorts(bootcampId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/bootcamps/{bootcamp_id}/cohorts", { params: { path: { bootcamp_id: bootcampId } } }),
      ),
  });
}

export function cohortQuery(id: string) {
  return queryOptions({
    queryKey: academyKeys.cohort(id),
    queryFn: () => unwrap(api.GET("/api/v1/admin/cohorts/{cohort_id}", { params: { path: { cohort_id: id } } })),
  });
}

/** 수강생 상태별 인원·배정 멘토·담당자 (A96) */
export function cohortSummaryQuery(id: string) {
  return queryOptions({
    queryKey: academyKeys.summary(id),
    queryFn: () =>
      unwrap(api.GET("/api/v1/admin/cohorts/{cohort_id}/summary", { params: { path: { cohort_id: id } } })),
  });
}

/** 기수 멘토링 설정. 아직 없으면 null (404 `mentoring_settings_not_configured`, A34) */
export function cohortSettingsQuery(id: string) {
  return queryOptions({
    queryKey: academyKeys.settings(id),
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/admin/cohorts/{cohort_id}/mentoring-settings", {
        params: { path: { cohort_id: id } },
      });
      if (response.status === 404) return null;
      if (error || !data) throw new Error("mentoring settings");
      return data;
    },
  });
}

/** 과정 운영 항목: 사용 여부·Airtable 별칭(PATCH), 담당 팀(PUT). 바뀐 것만 보낸다 */
export function useSaveBootcamp(bootcamp: Bootcamp) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      values,
      teamChange,
    }: {
      values: { is_active?: boolean; airtable_cohort_prefix?: string | null };
      teamChange?: { team_id: string | null };
    }) => {
      if (Object.keys(values).length)
        await unwrap(
          api.PATCH("/api/v1/admin/bootcamps/{bootcamp_id}", {
            params: { path: { bootcamp_id: bootcamp.id } },
            body: values,
          }),
        );
      if (teamChange)
        await unwrap(
          api.PUT("/api/v1/admin/bootcamps/{bootcamp_id}/team", {
            params: { path: { bootcamp_id: bootcamp.id } },
            body: teamChange,
          }),
        );
    },
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: academyKeys.bootcamps() }),
        client.invalidateQueries({ queryKey: orgKeys.all }),
      ]),
  });
}

/** 기수 운영 항목: 상태·디스코드 서버 ID */
export function useSaveCohort(cohort: Cohort) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { status?: CohortStatus; discord_guild_id?: string | null }) =>
      unwrap(api.PATCH("/api/v1/admin/cohorts/{cohort_id}", { params: { path: { cohort_id: cohort.id } }, body })),
    onSuccess: (saved) => {
      client.setQueryData(academyKeys.cohort(cohort.id), saved);
      return client.invalidateQueries({ queryKey: academyKeys.cohorts(cohort.bootcamp_id) });
    },
  });
}
