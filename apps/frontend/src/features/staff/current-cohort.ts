import type { StaffCohort } from "./api";

const KEY = "oz.admin.current-cohort";
const RECENT_KEY = "oz.admin.recent-cohorts";
const RECENT_MAX = 3;

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
  pushRecentCohort(id);
}

/** 최근에 고른 기수에만 더한다 (현재 기수는 그대로) */
export function pushRecentCohort(id: string): void {
  try {
    const recent = [id, ...recentCohortIds().filter((x) => x !== id)].slice(0, RECENT_MAX);
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
  } catch {
    // 저장소를 못 쓰면 기억하지 않는다
  }
}

/** 행정 업무의 과정·기수 선택 (F96): 멘토링 현재 기수와 따로 기억한다 */
export interface AdminScope {
  bootcamp?: string;
  cohort?: string;
}
const ADMIN_SCOPE_KEY = "oz.admin.administration-scope";

export function rememberedAdminScope(): AdminScope | null {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(ADMIN_SCOPE_KEY) ?? "null");
    if (!raw || typeof raw !== "object") return null;
    const { bootcamp, cohort } = raw as Record<string, unknown>;
    if (typeof cohort === "string") return { cohort };
    if (typeof bootcamp === "string") return { bootcamp };
    return null;
  } catch {
    return null;
  }
}

export function rememberAdminScope(scope: AdminScope): void {
  try {
    localStorage.setItem(ADMIN_SCOPE_KEY, JSON.stringify(scope));
  } catch {
    // 저장소를 못 쓰면 기억하지 않는다
  }
}

/** 최근에 고른 기수 (최신 먼저, 3개까지) */
export function recentCohortIds(): string[] {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

/** 처음 보여 줄 기수: 마지막으로 고른 기수 → 진행 중인 첫 기수 → 목록의 첫 기수 */
export function defaultCohort(cohorts: readonly StaffCohort[]): StaffCohort | undefined {
  const list = pickableCohorts(cohorts);
  const remembered = rememberedCohortId();
  return list.find((c) => c.id === remembered) ?? list.find((c) => c.status === "ONGOING") ?? list[0];
}
