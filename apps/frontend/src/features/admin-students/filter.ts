import type { RosterStudent } from "./api";

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
