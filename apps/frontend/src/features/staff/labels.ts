import type { StaffAccess, StaffCohort } from "./api";

/**
 * 사용자 메뉴의 역할 줄 (F58·A87): 최고 관리자면 '최고 관리자', 그다음 직위(= 역할)와 데이터 범위
 */
export function roleLines(access: Pick<StaffAccess, "is_super_admin" | "position"> | undefined): string[] {
  if (!access) return [];
  const lines: string[] = [];
  if (access.is_super_admin) lines.push("최고 관리자");
  if (access.position) {
    lines.push(`${access.position.name} · ${access.position.all_data ? "모든 과정·기수" : "담당 과정·기수"}`);
  }
  return lines;
}

export function staffCohortLabel(c: Pick<StaffCohort, "bootcamp_name" | "cohort_number">): string {
  return `${c.bootcamp_name} ${c.cohort_number}기`;
}
