import type { BadgeProps } from "@/components/ui/badge";

import type { EnrollmentStatus } from "./api";

type Tone = NonNullable<BadgeProps["variant"]>;

export const ENROLLMENT: Record<EnrollmentStatus, { label: string; badge: Tone }> = {
  ENROLLED: { label: "수강 중", badge: "info" },
  COMPLETED: { label: "수료", badge: "success" },
  DROPPED: { label: "중도 포기", badge: "secondary" },
  EARLY_EMPLOYED: { label: "조기 취업", badge: "secondary" },
  TRANSFERRED: { label: "기수 이동", badge: "secondary" },
};

export const ENROLLMENT_ORDER: EnrollmentStatus[] = [
  "ENROLLED",
  "COMPLETED",
  "DROPPED",
  "EARLY_EMPLOYED",
  "TRANSFERRED",
];

/** HRD 상태: Airtable `HRD상태` 원문 (academy roster.py) */
export const HRD_STATUS: Record<string, string> = {
  REGISTERED: "모집 중",
  TRAINING: "수강 중",
  COMPLETED: "정상 수료",
  COMPLETED_80_PERCENT: "80% 이상 수료",
  COMPLETED_AND_EMPLOYED: "수료 후 취업",
  EARLY_EMPLOYED: "조기 취업",
  WITHDRAWAL: "수강 철회",
  DROPPED_OUT: "중도 탈락",
  LEAVE: "하차",
  EXPELLED: "제적",
};

/** 'YYYY-MM-DD' → 'YYYY.MM.DD' */
export function dot(value: string | null | undefined): string {
  return value ? value.replaceAll("-", ".") : "—";
}
