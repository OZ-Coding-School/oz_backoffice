import { z } from "zod";

import { NO_TEAM, scopeOf, type StaffOptions } from "@/features/auth/staff-api";
import { staffFormSchema } from "@/features/auth/staff-form";

import type { Employee, EmployeeUpdate } from "./api";

/** 직원 수정 폼: 운영진 신청 폼(F26)에 최고 관리자를 더한다 (A90) */
export const employeeFormSchema = staffFormSchema.extend({ is_super_admin: z.boolean() });
export type EmployeeFormValues = z.infer<typeof employeeFormSchema>;

/** 보는 사람이 고칠 수 있는 항목 (A89·A90) */
export interface Editable {
  /** 부서·팀·직위·고용 형태 (org.employee.manage) */
  org: boolean;
  /** 담당 (staff.assignment.manage) */
  assign: boolean;
  /** 최고 관리자 (최고 관리자만) */
  superAdmin: boolean;
}

/** 바뀐 항목 중 고칠 수 있는 것만 보낸다 (A89·A90) */
export function payload(
  options: StaffOptions,
  initial: EmployeeFormValues,
  v: EmployeeFormValues,
  editable: Editable,
): EmployeeUpdate {
  const body: EmployeeUpdate = {};
  if (editable.org) {
    if (v.department_id !== initial.department_id) body.department_id = v.department_id;
    if (v.team_id !== initial.team_id) body.team_id = v.team_id === NO_TEAM ? null : v.team_id;
    if (v.position_id !== initial.position_id) body.position_id = v.position_id;
    if (v.employment_type !== initial.employment_type)
      body.employment_type = v.employment_type as Employee["employment_type"];
  }
  const assignmentsChanged =
    v.position_id !== initial.position_id ||
    v.cohort_id !== initial.cohort_id ||
    [...v.bootcamp_ids].sort().join() !== [...initial.bootcamp_ids].sort().join();
  if (editable.assign && assignmentsChanged) {
    const scope = scopeOf(options, v.position_id);
    body.bootcamp_ids = scope === "COURSE" ? v.bootcamp_ids : [];
    body.cohort_ids = scope === "COHORT" && v.cohort_id ? [v.cohort_id] : [];
  }
  if (editable.superAdmin && v.is_super_admin !== initial.is_super_admin) body.is_super_admin = v.is_super_admin;
  return body;
}
