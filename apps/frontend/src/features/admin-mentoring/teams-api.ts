import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type AdminTeam = components["schemas"]["AdminTeamResponse"];
export type UnassignedStudent = components["schemas"]["StudentSummary"];
export type CohortAssignment = components["schemas"]["AssignmentResponse"];
export type GrantResult = components["schemas"]["GrantResponse"];
export type TeamCreateBody = components["schemas"]["TeamCreate"];

export const teamKeys = {
  list: (cohortId: string) => ["admin-mentoring", "teams", cohortId] as const,
  unassigned: (cohortId: string) => ["admin-mentoring", "teams", cohortId, "unassigned"] as const,
  mentors: (cohortId: string) => ["admin-mentoring", "teams", cohortId, "mentors"] as const,
};

/** 팀 관리 목록: 팀 계좌·대기 신청·세션 수 포함 (A108) */
export function teamsQuery(cohortId: string) {
  return queryOptions({
    queryKey: teamKeys.list(cohortId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/cohorts/{cohort_id}/mentoring-teams", { params: { path: { cohort_id: cohortId } } }),
      ),
  });
}

/** 팀이 없는 수강 중 수강생 (가입 여부 무관, A39) */
export function unassignedQuery(cohortId: string) {
  return queryOptions({
    queryKey: teamKeys.unassigned(cohortId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/cohorts/{cohort_id}/mentoring-teams/unassigned-students", {
          params: { path: { cohort_id: cohortId } },
        }),
      ),
  });
}

/** 팀 담당 멘토 후보: 그 기수에 활성 배정된 멘토 (A39) */
export function cohortMentorsQuery(cohortId: string) {
  return queryOptions({
    queryKey: teamKeys.mentors(cohortId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/cohorts/{cohort_id}/mentor-assignments", { params: { path: { cohort_id: cohortId } } }),
      ),
  });
}

export function useCreateTeam(cohortId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: TeamCreateBody) =>
      unwrap(
        api.POST("/api/v1/admin/cohorts/{cohort_id}/mentoring-teams", {
          params: { path: { cohort_id: cohortId } },
          body,
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: teamKeys.list(cohortId) }),
  });
}

export interface TeamGrantInput {
  /** 비우면 전체 팀 */
  teamIds: string[] | null;
  minutes: number | null;
  validFrom: string | null;
  validUntil: string | null;
  reason: string;
  /** 같은 지급을 두 번 보내지 않도록 창을 열 때 정한다 */
  idempotencyKey: string;
}

/** 팀 시간 일괄 지급 (A39·A40): 가능한 팀만 지급하고 나머지는 사유와 함께 돌려준다 */
export function useGrantTeams(cohortId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: TeamGrantInput) =>
      unwrap(
        api.POST("/api/v1/admin/cohorts/{cohort_id}/mentoring-balances/grants", {
          params: { path: { cohort_id: cohortId }, header: { "Idempotency-Key": v.idempotencyKey } },
          body: {
            target: v.teamIds ? "TEAMS" : "ALL_TEAMS",
            ids: v.teamIds ?? [],
            minutes: v.minutes,
            valid_from: v.validFrom,
            valid_until: v.validUntil,
            reason: v.reason,
          },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: teamKeys.list(cohortId) }),
  });
}
