import type { Me } from "@/features/auth/api";
import { ROLE_LABELS } from "@/features/auth/messages";

import type { StaffCohort } from "./api";

/**
 * 사용자 메뉴의 역할 줄 (F58): 전체 범위는 역할 이름만, 과정·기수 범위는 그 이름을 앞에 붙인다.
 * 이름은 담당 기수 목록(A81)에서 찾고, 못 찾으면 역할 이름만 쓴다
 */
export function roleLines(roles: Me["roles"], cohorts: readonly StaffCohort[]): string[] {
  const cohortNames = new Map(cohorts.map((c) => [c.id, `${c.bootcamp_name} ${c.cohort_number}기`]));
  const bootcampNames = new Map(cohorts.map((c) => [c.bootcamp_id, c.bootcamp_name]));
  const lines = roles.map((r) => {
    const role = ROLE_LABELS[r.role] ?? r.role;
    const scope =
      r.scope_type === "COHORT"
        ? cohortNames.get(r.scope_id ?? "")
        : r.scope_type === "BOOTCAMP"
          ? bootcampNames.get(r.scope_id ?? "")
          : undefined;
    return scope ? `${scope} ${role}` : role;
  });
  return [...new Set(lines)];
}
