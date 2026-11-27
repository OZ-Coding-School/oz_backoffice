import { formatKst } from "@/lib/datetime";

import type { MentorAssignment } from "./api";

const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

/** 정산 줄: 근거 계약(A110)의 조건. 시간당이면 정산 기준을 앞에 붙인다 (세션당은 진행 시간과 관계없다) */
export function payText(a: MentorAssignment): string {
  const c = a.contract;
  if (!c || c.unit_price == null) return "근거 계약 정보 없음";
  const parts =
    c.price_unit === "HOURLY"
      ? [
          c.mentoring_time_basis === "ACTUAL_DURATION" ? "실제 진행 시간 기준" : "신청 시간 기준",
          `시간당 ${won(c.unit_price)}`,
        ]
      : [`세션당 ${won(c.unit_price)}`];
  const noShow = c.no_show_pay_amount ?? 0;
  parts.push(noShow > 0 ? `노쇼 ${won(noShow)}` : "노쇼 없음");
  return parts.join(" · ");
}

const REASONS: Record<NonNullable<MentorAssignment["deactivation_reason"]>, string> = {
  EXPIRED: "기간 만료로 종료",
  MANUAL: "운영진이 종료",
  MENTOR_DEACTIVATED: "멘토 비활성화로 종료",
  CONTRACT_ENDED: "계약 종료로 종료",
};

/** 종료 줄: "기간 만료로 종료 · 2026.05.30" */
export function endText(a: MentorAssignment): string | null {
  if (a.is_active) return null;
  const reason = a.deactivation_reason ? REASONS[a.deactivation_reason] : "종료";
  return a.deactivated_at ? `${reason} · ${formatKst(a.deactivated_at, "yyyy.MM.dd")}` : reason;
}
