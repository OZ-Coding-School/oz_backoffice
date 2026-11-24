import { z } from "zod";

import { NO_TEAM, scopeOf, type StaffOptions, type StaffRegistration } from "./staff-api";

const MAX_ASSIGNMENTS = 20;

/** 폼을 채울 신청 값 (본인 신청 또는 운영진 승인 대상) */
export type StaffFormSource = Pick<
  StaffRegistration,
  "department_id" | "team_id" | "position_id" | "employment_type" | "assignments"
>;

export const staffFormSchema = z.object({
  department_id: z.string().min(1, "부서를 골라 주세요."),
  team_id: z.string().min(1, "팀을 골라 주세요."),
  position_id: z.string().min(1, "직위를 골라 주세요."),
  employment_type: z.string().min(1, "고용 형태를 골라 주세요."),
  bootcamp_ids: z.array(z.string()).max(MAX_ASSIGNMENTS, `과정은 ${MAX_ASSIGNMENTS}개까지 고를 수 있어요.`),
  cohort_bootcamp_id: z.string(),
  cohort_id: z.string(),
});
export type StaffFormValues = z.infer<typeof staffFormSchema>;

/** 신청(또는 승인할 신청)의 값으로 폼을 채운다 */
export function staffFormValues(options: StaffOptions, initial: StaffFormSource | null): StaffFormValues {
  const assistant = initial?.assignments.find((a) => a.role === "ASSISTANT" && a.cohort_id);
  const cohort = assistant ? options.cohorts.find((c) => c.id === assistant.cohort_id) : undefined;
  return {
    department_id: initial?.department_id ?? "",
    team_id: initial ? (initial.team_id ?? NO_TEAM) : "",
    position_id: initial?.position_id ?? "",
    employment_type: initial?.employment_type ?? "",
    bootcamp_ids: (initial?.assignments ?? [])
      .filter((a) => a.role === "MANAGER" && a.bootcamp_id)
      .map((a) => a.bootcamp_id as string),
    cohort_bootcamp_id: cohort?.bootcamp_id ?? "",
    cohort_id: cohort?.id ?? "",
  };
}

/** 폼 값 → 신청·승인 본문. 담당은 직위 방식대로, 팀이 없으면(부서 직속) 넓게 보지 않는 한 없다 (A62) */
export function staffPayload(options: StaffOptions, values: StaffFormValues, wide = false) {
  const scope = scopeOf(options, values.position_id);
  const withTeam = values.team_id !== NO_TEAM;
  return {
    department_id: values.department_id,
    team_id: withTeam ? values.team_id : null,
    position_id: values.position_id,
    employment_type: values.employment_type as StaffRegistration["employment_type"],
    assignments:
      !withTeam && !wide
        ? []
        : scope === "COURSE"
          ? values.bootcamp_ids.map((id) => ({ role: "MANAGER" as const, bootcamp_id: id, cohort_id: null }))
          : scope === "COHORT" && values.cohort_id
            ? [{ role: "ASSISTANT" as const, bootcamp_id: null, cohort_id: values.cohort_id }]
            : [],
  };
}
