import type { Position } from "@/features/admin-permissions/api";

/** 우선순위 간격: 순서를 저장할 때 10, 20, 30 … 으로 다시 매긴다 (F70) */
export const PRIORITY_STEP = 10;
const MAX_PRIORITY = 32767;

/** 목록 순서: 우선순위가 작을수록 위, 같으면 이름순 (서버와 같음) */
export function byPriority(a: Position, b: Position): number {
  return a.priority - b.priority || a.name.localeCompare(b.name, "ko");
}

/** from 자리의 항목을 to 자리로 옮긴 새 배열 */
export function move<T>(items: readonly T[], from: number, to: number): T[] {
  const next = [...items];
  const [item] = next.splice(from, 1);
  if (item === undefined) return next;
  next.splice(Math.max(0, Math.min(to, next.length)), 0, item);
  return next;
}

/** 순서가 바뀌었는가 */
export function orderChanged(before: readonly Position[], after: readonly Position[]): boolean {
  return before.some((p, i) => after[i]?.id !== p.id);
}

/**
 * 새 순서를 저장할 priority 변경 목록. 자리마다 (i+1)×10을 주고 지금 값과 다른 직위만 보낸다.
 * 같은 값을 가진 직위가 있어도 자리대로 정리된다.
 */
export function priorityChanges(ordered: readonly Position[]): { id: string; priority: number }[] {
  return ordered
    .map((p, i) => ({ id: p.id, priority: Math.min((i + 1) * PRIORITY_STEP, MAX_PRIORITY), before: p.priority }))
    .filter((c) => c.priority !== c.before)
    .map(({ id, priority }) => ({ id, priority }));
}

/** 새 직위의 priority: 맨 아래 */
export function nextPriority(positions: readonly Position[]): number {
  const max = positions.reduce((m, p) => Math.max(m, p.priority), 0);
  return Math.min(max + PRIORITY_STEP, MAX_PRIORITY);
}
