import type { StaffCohort } from "./api";

const KEY = "oz.admin.current-cohort";

/** 기수 단위 화면 주소 `/admin/cohorts/{id}/…`의 기수 id (F59·F90) */
export function cohortIdOf(pathname: string): string | null {
  return /^\/admin\/cohorts\/([^/]+)\//.exec(pathname)?.[1] ?? null;
}

/** 선택기 목록: 보관한 기수는 뺀다 (F90). 서버가 진행 중 → 예정 → 종료 → 비활성 순으로 준다 (A81) */
export function pickableCohorts(cohorts: readonly StaffCohort[]): StaffCohort[] {
  return cohorts.filter((c) => c.status !== "ARCHIVED");
}

/** 마지막으로 고른 기수 (브라우저에만, 못 읽으면 없음) */
export function rememberedCohortId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function rememberCohort(id: string): void {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    // 저장소를 못 쓰면 기억하지 않는다
  }
}

/** 처음 보여 줄 기수: 마지막으로 고른 기수 → 진행 중인 첫 기수 → 목록의 첫 기수 */
export function defaultCohort(cohorts: readonly StaffCohort[]): StaffCohort | undefined {
  const list = pickableCohorts(cohorts);
  const remembered = rememberedCohortId();
  return list.find((c) => c.id === remembered) ?? list.find((c) => c.status === "ONGOING") ?? list[0];
}
