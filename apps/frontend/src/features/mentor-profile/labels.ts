import type { MyAssignment } from "@/features/mentor-requests/api";

type TimeBasis = NonNullable<NonNullable<MyAssignment["contract"]>["mentoring_time_basis"]>;

/** 정산 시간 기준은 근거 계약에서 읽는다 (A110) */
export const POLICY_LABELS: Record<TimeBasis, string> = {
  ACTUAL_DURATION: "실제 진행 시간 정산",
  STUDENT_REQUEST: "신청 시간 정산",
};

function dateLabel(date: string): string {
  return date.replaceAll("-", ".");
}

/** "2026.11.01 ~ 2027.03.31" (끝이 없으면 '종료일 없음') */
export function assignmentPeriod(a: Pick<MyAssignment, "start_date" | "end_date">): string {
  return `${dateLabel(a.start_date)} ~ ${a.end_date ? dateLabel(a.end_date) : "종료일 없음"}`;
}

/** 배정된 기수 (F56): 종료까지 모두, 활성 먼저 그다음 최근 시작 순. 단가는 보여 주지 않는다 */
export function sortAssignments(items: readonly MyAssignment[]): MyAssignment[] {
  return [...items].sort(
    (a, b) => Number(b.is_active) - Number(a.is_active) || b.start_date.localeCompare(a.start_date),
  );
}
