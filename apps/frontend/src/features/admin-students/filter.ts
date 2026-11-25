import type { RosterStudent } from "./api";
import { ENROLLMENT, ENROLLMENT_ORDER } from "./labels";

/** 이름·휴대폰(숫자)·이메일 부분 일치 */
export function matches(s: RosterStudent, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  const digits = needle.replace(/\D/g, "");
  return (
    s.name.toLowerCase().includes(needle) ||
    (s.email ?? "").toLowerCase().includes(needle) ||
    (digits.length >= 3 && (s.phone_number ?? "").includes(digits))
  );
}

export type StudentGroupBy = "status" | "signup";

export interface StudentGroup {
  key: string;
  label: string;
  items: RosterStudent[];
}

/** 묶어 보기 (F77): 수강 상태는 상태 탭 순서, 가입 상태는 가입 → 미가입. 빈 묶음은 뺀다 */
export function groupStudents(students: readonly RosterStudent[], by: StudentGroupBy): StudentGroup[] {
  const groups: StudentGroup[] =
    by === "status"
      ? ENROLLMENT_ORDER.map((st) => ({
          key: st,
          label: ENROLLMENT[st].label,
          items: students.filter((s) => s.status === st),
        }))
      : [
          { key: "signed", label: "가입", items: students.filter((s) => s.user_id) },
          { key: "unsigned", label: "미가입", items: students.filter((s) => !s.user_id) },
        ];
  return groups.filter((g) => g.items.length > 0);
}
