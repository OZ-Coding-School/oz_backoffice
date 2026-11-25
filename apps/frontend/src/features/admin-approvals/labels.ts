import type { BadgeProps } from "@/components/ui/badge";
import { ENROLLMENT_STATUS_LABELS } from "@/features/member/api";
import { formatKst } from "@/lib/datetime";

import type { Applicant, ContractCandidate, StudentCandidate } from "./api";

type Tone = NonNullable<BadgeProps["variant"]>;

/** 자동 매칭 결과 (A31·A105): 대기는 명단·가입 전 멘토가 없거나 여러 명일 때 */
export function matchLabel(a: Applicant): { label: string; badge: Tone } {
  if (a.signup.match_result === "AMBIGUOUS") return { label: "후보 여러 명", badge: "info" };
  return { label: a.signup.signup_type === "MENTOR" ? "가입 전 멘토 없음" : "명단 없음", badge: "warning" };
}

export function requestedCohort(a: Applicant): string {
  return a.requested_bootcamp_name && a.requested_cohort_number
    ? `${a.requested_bootcamp_name} ${a.requested_cohort_number}기`
    : "—";
}

export function appliedAt(a: Applicant): string {
  return a.signup.created_at ? formatKst(a.signup.created_at, "MM/dd") : "—";
}

export function enrollmentLabel(status: string): string {
  return ENROLLMENT_STATUS_LABELS[status as keyof typeof ENROLLMENT_STATUS_LABELS] ?? status;
}

/** 이름·휴대폰 일치 태그 (A82) */
export function matchTag(c: Pick<StudentCandidate | ContractCandidate, "name_match" | "phone_match">): string {
  if (c.name_match && c.phone_match) return "이름·휴대폰 일치";
  if (c.name_match) return "휴대폰 다름";
  if (c.phone_match) return "이름 다름";
  return "이름·휴대폰 다름";
}

export function studentCandidateCohort(c: Pick<StudentCandidate, "bootcamp_name" | "cohort_number">): string {
  return c.bootcamp_name && c.cohort_number ? `${c.bootcamp_name} ${c.cohort_number}기` : "기수 정보 없음";
}
