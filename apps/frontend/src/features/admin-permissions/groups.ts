import type { PermissionDef, Position } from "./api";

/** 엔터티 한 행: [조회] [관리·동작] (A86) */
export interface EntityRow {
  entity: string;
  read: PermissionDef | null;
  action: PermissionDef | null;
}

export interface PermissionGroup {
  area: string;
  rows: EntityRow[];
  codes: string[];
}

/** 권한 정의 → 영역별 엔터티 행 (정의 순서를 지킨다) */
export function buildGroups(defs: readonly PermissionDef[]): PermissionGroup[] {
  const groups: PermissionGroup[] = [];
  for (const def of defs) {
    let group = groups.find((g) => g.area === def.area);
    if (!group) {
      group = { area: def.area, rows: [], codes: [] };
      groups.push(group);
    }
    group.codes.push(def.code);
    let row = group.rows.find((r) => r.entity === def.entity);
    if (!row) {
      row = { entity: def.entity, read: null, action: null };
      group.rows.push(row);
    }
    if (def.action === "조회") row.read = def;
    else row.action = def;
  }
  return groups;
}

/**
 * 권한 하나를 켜고 끈다. 관리·동작을 켜면 조회도 켜고, 조회를 끄면 그 조회가 필요한 권한도 끈다 (A86)
 */
export function toggle(
  selected: ReadonlySet<string>,
  def: PermissionDef,
  on: boolean,
  defs: readonly PermissionDef[],
): Set<string> {
  const next = new Set(selected);
  if (on) {
    next.add(def.code);
    if (def.requires) next.add(def.requires);
  } else {
    next.delete(def.code);
    for (const d of defs) if (d.requires === def.code) next.delete(d.code);
  }
  return next;
}

export interface PermissionChange {
  code: string;
  label: string;
  on: boolean;
}

/** 저장 전과 지금의 차이 (정의 순서). label은 '기수 · 조회' */
export function diff(
  before: ReadonlySet<string>,
  after: ReadonlySet<string>,
  defs: readonly PermissionDef[],
): PermissionChange[] {
  return defs
    .filter((d) => before.has(d.code) !== after.has(d.code))
    .map((d) => ({ code: d.code, label: `${d.entity} · ${d.action}`, on: after.has(d.code) }));
}

/** 저장 본문: 정의 순서의 코드 목록 */
export function orderedCodes(selected: ReadonlySet<string>, defs: readonly PermissionDef[]): string[] {
  return defs.filter((d) => selected.has(d.code)).map((d) => d.code);
}

export function assignmentScopeLabel(scope: Position["assignment_scope"]): string {
  return scope === "COURSE" ? "과정 담당" : scope === "COHORT" ? "기수 담당" : "담당 없음";
}

export function dataScopeLabel(scope: Position["data_scope"]): string {
  return scope === "ALL" ? "모든 과정·기수" : "담당 과정·기수만";
}

/** 왼쪽 목록의 한 줄 설명: '담당만 · 과정 담당 · 직원 6명' */
export function positionLine(p: Position): string {
  return `${p.data_scope === "ALL" ? "전체 데이터" : "담당만"} · ${assignmentScopeLabel(p.assignment_scope)} · 직원 ${p.employee_count}명`;
}
