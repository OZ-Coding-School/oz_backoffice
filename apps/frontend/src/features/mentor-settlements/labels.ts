import { formatKst } from "@/lib/datetime";

import type { SettlementDetail, SettlementItem, SettlementSummary } from "./api";

/** 1234567 → "1,234,567원" */
export function won(amount: number): string {
  return `${amount.toLocaleString("ko-KR")}원`;
}

/** 정산 기수 "백엔드 부트캠프 12기" (A80). 이름이 없으면 null */
export function cohortLabel(s: Pick<SettlementSummary, "bootcamp_name" | "cohort_number">): string | null {
  return s.bootcamp_name && s.cohort_number ? `${s.bootcamp_name} ${s.cohort_number}기` : null;
}

/** "2026-10" → "2026년 10월" */
export function monthTitle(month: string): string {
  const [year, m] = month.split("-");
  return `${year}년 ${Number(m)}월`;
}

/** 마감일 "11/05 마감" (KST) */
export function closedLabel(s: Pick<SettlementSummary, "closed_at">): string | null {
  return s.closed_at ? `${formatKst(s.closed_at, "MM/dd")} 마감` : null;
}

function previousMonth(month: string): string {
  const [year, m] = month.split("-").map(Number) as [number, number];
  return m === 1 ? `${year - 1}-12` : `${year}-${String(m - 1).padStart(2, "0")}`;
}

export interface SummaryCard {
  label: string;
  amount: number;
  note: string;
}

function monthCard(items: readonly SettlementSummary[], month: string): SummaryCard {
  const inMonth = items.filter((s) => s.month === month);
  const cohorts = new Set(inMonth.map((s) => s.cohort_id)).size;
  const sessions = inMonth.reduce((sum, s) => sum + s.session_count, 0);
  return {
    label: `${Number(month.split("-")[1])}월 정산 합계`,
    amount: inMonth.reduce((sum, s) => sum + s.total_amount, 0),
    note: inMonth.length ? `${cohorts}개 기수 · 세션 ${sessions}회` : "정산 없음",
  };
}

/**
 * 목록 위 요약 3칸 (F54): 가장 최근 달 합계 · 그 전 달 합계 · 올해(KST) 누적.
 * 받은(기수로 거른) 마감 정산으로 계산한다. 정산이 없으면 빈 배열
 */
export function summaryCards(items: readonly SettlementSummary[], now: number): SummaryCard[] {
  const latest = items.reduce<string | null>((max, s) => (max === null || s.month > max ? s.month : max), null);
  if (latest === null) return [];
  const year = formatKst(now, "yyyy");
  const thisYear = items.filter((s) => s.month.startsWith(`${year}-`));
  return [
    monthCard(items, latest),
    monthCard(items, previousMonth(latest)),
    {
      label: "올해 누적",
      amount: thisYear.reduce((sum, s) => sum + s.total_amount, 0),
      note: `${thisYear.length}개 정산서`,
    },
  ];
}

const POLICY_LABELS: Record<SettlementItem["settlement_policy"], string> = {
  ACTUAL_DURATION: "실제 진행 시간",
  STUDENT_REQUEST: "신청 시간",
};

/** 단가 "30,000원/시간" */
export function unitPrice(item: Pick<SettlementItem, "pay_unit" | "pay_rate">): string {
  const rate = won(item.pay_rate);
  switch (item.pay_unit) {
    case "HOURLY":
      return `${rate}/시간`;
    case "PER_SESSION":
      return `${rate}/회`;
    case "MONTHLY":
      return `${rate}/월`;
    case "LUMP_SUM":
      return `${rate} 일괄`;
  }
}

/**
 * 정산서 머리 설명: "정산 기준 실제 진행 시간 · 30,000원/시간 · 11/05 마감".
 * 세션 항목의 기준·단가가 하나면 보여 주고, 여러 개면 뺀다 (항목마다 보인다)
 */
export function detailSubtitle(s: SettlementDetail): string {
  const sessions = s.items.filter((i) => i.item_type === "SESSION");
  const policies = new Set(sessions.map((i) => i.settlement_policy));
  const prices = new Set(sessions.map(unitPrice));
  const [policy] = policies;
  const [price] = prices;
  return [
    policies.size === 1 && policy ? `정산 기준 ${POLICY_LABELS[policy]}` : null,
    prices.size === 1 ? price : null,
    closedLabel(s),
  ]
    .filter(Boolean)
    .join(" · ");
}

/** 명세 항목 상대 "가수강 · 1:1" / "3팀 알파 · 팀" (A80) */
export function counterpartLabel(item: SettlementItem): string {
  if (item.team_label) return `${item.team_label} · 팀`;
  return `${item.requester_name ?? "—"} · 1:1`;
}

export function itemTypeLabel(item: SettlementItem): { label: string; badge: "secondary" | "warning" } {
  return item.item_type === "NO_SHOW" ? { label: "노쇼", badge: "warning" } : { label: "세션", badge: "secondary" };
}
