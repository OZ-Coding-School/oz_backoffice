import type { BadgeProps } from "@/components/ui/badge";
import { formatKst, formatKstDay, formatMinutes } from "@/lib/datetime";

import type { MentoringRequest, RequestStatus } from "./api";

type Tone = NonNullable<BadgeProps["variant"]>;

/** 상태 배지·띠·배경 (F14: 상태 색은 배지·띠·배경에만) */
export const STATUS_STYLE: Record<RequestStatus, { label: string; badge: Tone; card: string; bar: string }> = {
  PENDING: { label: "승인 대기", badge: "primary", card: "bg-accent", bar: "bg-primary" },
  APPROVED: { label: "승인", badge: "success", card: "bg-success-subtle", bar: "bg-success" },
  REJECTED: { label: "반려", badge: "destructive", card: "bg-destructive-subtle", bar: "bg-destructive" },
  CANCELED: { label: "취소", badge: "warning", card: "bg-warning-subtle", bar: "bg-warning" },
};

/** 차감 상태 한 줄 (A66 balance). 팀 신청은 '팀 계좌'를 앞에 붙인다 */
export function balanceLine(request: Pick<MentoringRequest, "balance" | "team_id">): string | null {
  const { state, minutes } = request.balance;
  const team = request.team_id ? "팀 계좌 " : "";
  switch (state) {
    case "HELD":
      return `${team}차감 예정 ${formatMinutes(minutes)}`;
    case "USED":
      return `${team}${formatMinutes(minutes)} 차감`;
    case "RETURNED":
      return "시간 돌려받음";
    case "NONE":
      return null;
  }
}

export function kindLabel(request: Pick<MentoringRequest, "team_id" | "team_label">): string {
  return request.team_id ? `팀 멘토링 · ${request.team_label ?? "팀"}` : "1:1 멘토링";
}

/** "11/24(화) 19:00 ~ 20:00" */
export function slotLabel(startsAt: string, minutes: number): string {
  const end = new Date(new Date(startsAt).getTime() + minutes * 60_000);
  return `${formatKstDay(startsAt)} ${formatKst(startsAt, "HH:mm")} ~ ${formatKst(end, "HH:mm")}`;
}

/** 확정 일시 (승인된 신청, A66 session) */
export function sessionLabel(session: NonNullable<MentoringRequest["session"]>): string {
  return `${formatKstDay(session.starts_at)} ${formatKst(session.starts_at, "HH:mm")} ~ ${formatKst(session.ends_at, "HH:mm")}`;
}

/** 취소 안내 꼬리: "(11/06 12:30 본인 취소)". 취소 주체가 없으면(A66 이전) 시각만 */
export function canceledTail(
  request: Pick<MentoringRequest, "canceled_at" | "canceled_by" | "requester_name">,
  mine: boolean,
): string | null {
  if (!request.canceled_at) return null;
  const at = formatKst(request.canceled_at, "MM/dd HH:mm");
  const who = actorLabel(request, mine);
  return who ? `${at} ${who} 취소` : `${at} 취소`;
}

function actorLabel(request: Pick<MentoringRequest, "canceled_by" | "requester_name">, mine: boolean): string | null {
  switch (request.canceled_by) {
    case "REQUESTER":
      return mine ? "본인" : request.requester_name;
    case "MENTOR":
      return "멘토";
    case "STAFF":
      return "운영진";
    case "SYSTEM":
      return "자동";
    default:
      return null;
  }
}

export type CancelState = { kind: "none" } | { kind: "available"; deadline: Date | null } | { kind: "deadline_passed" };

/**
 * 신청자가 지금 취소할 수 있는지 (A42·M26·F29).
 * - 신청자(1:1 본인, 팀 신청은 신청한 팀원)만
 * - 승인 대기는 언제든, 승인된 신청은 시작 minLeadHours 시간 전까지
 */
export function cancelState(
  request: Pick<MentoringRequest, "status" | "session">,
  { mine, minLeadHours, now }: { mine: boolean; minLeadHours: number | undefined; now: Date },
): CancelState {
  if (!mine) return { kind: "none" };
  if (request.status === "PENDING") return { kind: "available", deadline: null };
  if (request.status !== "APPROVED" || !request.session || minLeadHours === undefined) return { kind: "none" };
  const deadline = new Date(new Date(request.session.starts_at).getTime() - minLeadHours * 3_600_000);
  return now <= deadline ? { kind: "available", deadline } : { kind: "deadline_passed" };
}
