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
