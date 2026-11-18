import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type StaffOptions = components["schemas"]["StaffRegistrationOptionsResponse"];
export type StaffRegistration = components["schemas"]["StaffRegistrationResponse"];
export type StaffRegistrationRequest = components["schemas"]["StaffRegistrationRequest"];
export type StaffRole = components["schemas"]["StaffRole"];

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

/** 부서 표시 이름: 상위 부서가 있으면 '상위 › 하위' (decisions F25) */
export function departmentLabels(departments: StaffOptions["departments"]): { id: string; label: string }[] {
  const byId = new Map(departments.map((d) => [d.id, d]));
  const path = (id: string, seen = new Set<string>()): string => {
    const d = byId.get(id);
    if (!d) return "";
    if (!d.parent_id || seen.has(d.parent_id) || !byId.has(d.parent_id)) return d.name;
    seen.add(id);
    return `${path(d.parent_id, seen)} › ${d.name}`;
  };
  return departments.map((d) => ({ id: d.id, label: path(d.id) })).sort((a, b) => a.label.localeCompare(b.label, "ko"));
}

/** 담당 대상 값: 과정 전체 `bootcamp:<id>` 또는 기수 `cohort:<id>` */
export type TargetValue = `bootcamp:${string}` | `cohort:${string}`;

export function targetOptions(options: StaffOptions, role: StaffRole): { value: TargetValue; label: string }[] {
  const bootcampName = new Map(options.bootcamps.map((b) => [b.id, b.name]));
  const cohorts = options.cohorts.map((c) => ({
    value: `cohort:${c.id}` as TargetValue,
    label: `${bootcampName.get(c.bootcamp_id) ?? ""} ${c.cohort_number}기`.trim(),
  }));
  if (role === "ASSISTANT") return cohorts; // 조교는 기수만 (A11)
  return [
    ...options.bootcamps.map((b) => ({ value: `bootcamp:${b.id}` as TargetValue, label: `${b.name} (과정 전체)` })),
    ...cohorts,
  ];
}

export function toTargetValue(a: { bootcamp_id?: string | null; cohort_id?: string | null }): TargetValue | "" {
  if (a.cohort_id) return `cohort:${a.cohort_id}`;
  if (a.bootcamp_id) return `bootcamp:${a.bootcamp_id}`;
  return "";
}

export function fromTargetValue(value: string): { bootcamp_id: string | null; cohort_id: string | null } {
  const [kind, id = ""] = value.split(":");
  return kind === "cohort" ? { bootcamp_id: null, cohort_id: id } : { bootcamp_id: id, cohort_id: null };
}
