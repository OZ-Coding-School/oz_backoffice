import type { BadgeProps } from "@/components/ui/badge";

import type { CohortStatus } from "./api";

export const COHORT_STATUS: Record<CohortStatus, { label: string; variant: NonNullable<BadgeProps["variant"]> }> = {
  PLANNED: { label: "개강 전", variant: "info" },
  ONGOING: { label: "진행 중", variant: "success" },
  ENDED: { label: "종료", variant: "secondary" },
  INACTIVE: { label: "비활성", variant: "warning" },
  ARCHIVED: { label: "보관", variant: "outline" },
};

export const COHORT_STATUS_ORDER: CohortStatus[] = ["PLANNED", "ONGOING", "ENDED", "INACTIVE", "ARCHIVED"];

/** 기간: '2026.06.02 ~ 2026.11.30' */
export function periodLabel(start: string, end: string): string {
  return `${start.replaceAll("-", ".")} ~ ${end.replaceAll("-", ".")}`;
}

/** HRD: 'AIG… · 9회차' */
export function hrdLabel(hrdNetId: string | null | undefined, cohortNumber?: number | null): string {
  if (!hrdNetId && !cohortNumber) return "—";
  return [hrdNetId ?? "ID 없음", cohortNumber ? `${cohortNumber}회차` : null].filter(Boolean).join(" · ");
}

/** 운영시간 '10:00~19:00' 또는 '운영 안 함' */
export function hoursLabel(hours: { start: string; end: string } | null | undefined): string {
  return hours ? `${hours.start}~${hours.end}` : "운영 안 함";
}

export const TRAIN_TYPE_LABELS: Record<string, string> = { KDT: "KDT", KDC: "KDC" };
export const WEEKEND_LABELS: Record<string, string> = { WEEKDAY: "평일", WEEKEND: "주말", HYBRID: "평일·주말" };
export const DAY_NIGHT_LABELS: Record<string, string> = { DAY: "주간", NIGHT: "야간", HYBRID: "주야간" };

/** 금액 '11,200,000원' (없으면 '—') */
export function won(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toLocaleString("ko-KR")}원`;
}

/** 숫자 + 단위 (없으면 '—') */
export function amount(value: number | null | undefined, unit: string): string {
  return value === null || value === undefined ? "—" : `${value.toLocaleString("ko-KR")}${unit}`;
}

/** 기간 'YYYY.MM.DD ~ YYYY.MM.DD' (한쪽이 없으면 그쪽을 비움) */
export function optionalPeriod(start: string | null | undefined, end: string | null | undefined): string {
  if (!start && !end) return "—";
  return `${start ? start.replaceAll("-", ".") : ""} ~ ${end ? end.replaceAll("-", ".") : ""}`.trim();
}
