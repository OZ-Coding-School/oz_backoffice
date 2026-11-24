import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type StaffOptions = components["schemas"]["StaffRegistrationOptionsResponse"];
export type StaffRegistration = components["schemas"]["StaffRegistrationResponse"];
export type StaffRegistrationRequest = components["schemas"]["StaffRegistrationRequest"];

export const staffKeys = {
  options: ["staff-registration", "options"] as const,
  mine: ["staff-registration", "mine"] as const,
};

export const staffOptionsQuery = queryOptions({
  queryKey: staffKeys.options,
  queryFn: () => unwrap(api.GET("/api/v1/me/staff-registration/options")),
  staleTime: 5 * 60_000,
});

/** 내 운영진 정보 입력 (아직 없으면 null) */
export const staffRegistrationQuery = queryOptions({
  queryKey: staffKeys.mine,
  queryFn: async () => (await unwrap(api.GET("/api/v1/me/staff-registration"))) ?? null,
});

export function submitStaffRegistration(body: StaffRegistrationRequest) {
  return unwrap(api.PUT("/api/v1/me/staff-registration", { body }));
}

export type AssignmentScope = NonNullable<StaffOptions["positions"][number]["assignment_scope"]>;

/** 팀 칸 값: 팀 id, 또는 팀 없이 부서 직속 (A62) */
export const NO_TEAM = "none";

/** 고른 부서의 팀 (이름순) */
export function teamsOf(options: StaffOptions, departmentId: string) {
  return options.teams
    .filter((t) => t.department_id === departmentId)
    .sort((a, b) => a.name.localeCompare(b.name, "ko"));
}

/** 팀이 담당하는 과정 (이름순). 팀이 없으면(부서 직속) 없다 (A62) */
export function teamBootcamps(options: StaffOptions, teamId: string | null) {
  if (!teamId || teamId === NO_TEAM) return [];
  return options.bootcamps.filter((b) => b.team_id === teamId).sort((a, b) => a.name.localeCompare(b.name, "ko"));
}

/** 과정의 기수 (회차순). 승인된 조교가 있는 기수는 서버가 이미 뺐다 (A63) */
export function bootcampCohorts(options: StaffOptions, bootcampId: string) {
  return options.cohorts.filter((c) => c.bootcamp_id === bootcampId).sort((a, b) => a.cohort_number - b.cohort_number);
}

export function scopeOf(options: StaffOptions, positionId: string): AssignmentScope | null {
  return options.positions.find((p) => p.id === positionId)?.assignment_scope ?? null;
}

/** 담당 표시 이름: 과정은 과정 이름, 기수는 '과정 N기' */
export function assignmentLabel(
  options: StaffOptions,
  a: { bootcamp_id?: string | null; cohort_id?: string | null },
): string | null {
  const bootcampName = (id: string) => options.bootcamps.find((b) => b.id === id)?.name;
  if (a.cohort_id) {
    const cohort = options.cohorts.find((c) => c.id === a.cohort_id);
    if (!cohort) return null;
    return `${bootcampName(cohort.bootcamp_id) ?? ""} ${cohort.cohort_number}기`.trim();
  }
  return a.bootcamp_id ? (bootcampName(a.bootcamp_id) ?? null) : null;
}
