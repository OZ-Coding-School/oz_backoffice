import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type StaffAccess = components["schemas"]["StaffAccessResponse"];
export type StaffCohort = components["schemas"]["StaffCohortResponse"];

/** 운영진 유효 권한·담당 기수 (A81). 틀이 메뉴를 고르고 화면이 버튼을 숨길 때 쓴다 (F17) */
export const staffAccessQuery = queryOptions({
  queryKey: ["staff-access"] as const,
  queryFn: () => unwrap(api.GET("/api/v1/me/staff-access")),
  staleTime: 5 * 60_000,
});

/** 그 권한이 어느 범위로든 있는가 (메뉴·버튼 숨김. 최종 판정은 서버 403, F17) */
export function hasPermission(access: Pick<StaffAccess, "permissions">, code: string): boolean {
  return access.permissions.some((p) => p.code === code);
}

/** 그 권한이 이 기수에 미치는가 (최고 관리자·전체 범위·과정 범위·기수 범위). 최종 판정은 서버 403 */
export function hasPermissionIn(
  access: Pick<StaffAccess, "is_super_admin" | "permissions">,
  code: string,
  cohort: Pick<StaffCohort, "id" | "bootcamp_id">,
): boolean {
  if (access.is_super_admin) return true;
  return access.permissions.some(
    (p) =>
      p.code === code &&
      (p.is_global || p.cohort_ids.includes(cohort.id) || p.bootcamp_ids.includes(cohort.bootcamp_id)),
  );
}
