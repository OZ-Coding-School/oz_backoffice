import type { BadgeProps } from "@/components/ui/badge";

import type { EnrollmentStatus } from "./api";

type Tone = NonNullable<BadgeProps["variant"]>;

/** 수강 상태 배지와 묶음 머리 배경 (F77) */
export const ENROLLMENT: Record<EnrollmentStatus, { label: string; badge: Tone; tint: string }> = {
  ENROLLED: { label: "수강 중", badge: "info", tint: "bg-info/20" },
  COMPLETED: { label: "수료", badge: "success", tint: "bg-success/20" },
  DROPPED: { label: "중도 포기", badge: "destructive", tint: "bg-destructive/20" },
  EARLY_EMPLOYED: { label: "조기 취업", badge: "success", tint: "bg-success/20" },
  TRANSFERRED: { label: "기수 이동", badge: "warning", tint: "bg-warning/25" },
};

/** 가입 상태 묶음 (F77) */
export const SIGNUP: Record<"signed" | "unsigned", { label: string; badge: Tone; tint: string }> = {
  signed: { label: "가입", badge: "default", tint: "bg-primary/20" },
  unsigned: { label: "미가입", badge: "secondary", tint: "bg-muted-foreground/20" },
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
