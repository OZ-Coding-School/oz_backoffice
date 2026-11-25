import type { components } from "@/api/schema.gen";
import { formatKst } from "@/lib/datetime";

import type { MentorAssignment } from "./api";

type Cohort = components["schemas"]["MentorCohortItem"];

/** "백엔드 12기 · 데이터 분석 3기" */
export function cohortsText(cohorts: readonly Cohort[]): string {
  return cohorts.map((c) => `${c.bootcamp_name} ${c.cohort_number}기`).join(" · ");
}

const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

/** 정산 줄: 시간당이면 정산 기준을 앞에 붙인다 (세션당은 진행 시간과 관계없다) */
export function payText(a: MentorAssignment): string {
  const parts =
    a.pay_unit === "HOURLY"
      ? [
          a.cost_settlement_policy === "ACTUAL_DURATION" ? "실제 진행 시간 기준" : "신청 시간 기준",
          `시간당 ${won(a.pay_rate)}`,
        ]
      : [`세션당 ${won(a.pay_rate)}`];
  parts.push(a.no_show_pay_amount > 0 ? `노쇼 ${won(a.no_show_pay_amount)}` : "노쇼 없음");
  return parts.join(" · ");
}

const REASONS: Record<NonNullable<MentorAssignment["deactivation_reason"]>, string> = {
  EXPIRED: "기간 만료로 종료",
  MANUAL: "운영진이 종료",
  MENTOR_DEACTIVATED: "멘토 비활성화로 종료",
};

/** 종료 줄: "기간 만료로 종료 · 2026.05.30" */
export function endText(a: MentorAssignment): string | null {
  if (a.is_active) return null;
  const reason = a.deactivation_reason ? REASONS[a.deactivation_reason] : "종료";
  return a.deactivated_at ? `${reason} · ${formatKst(a.deactivated_at, "yyyy.MM.dd")}` : reason;
}
