import type { BadgeProps } from "@/components/ui/badge";
import { canceledTail } from "@/features/requests/labels";
import { formatKst, formatKstDay, formatMinutes, toEpochMs } from "@/lib/datetime";

import type { MentoringSession, SessionStatus } from "./api";

type Tone = NonNullable<BadgeProps["variant"]>;

/** 상태 배지·띠·배경 (F14: 상태 색은 배지·띠·배경에만). 진행 중은 예정과 같은 색에 배지만 따로 (F33) */
export const STATUS_STYLE: Record<
  SessionStatus,
  { label: string; badge: Tone; card: string; side: string; bar: string }
> = {
  SCHEDULED: { label: "예정", badge: "primary", card: "bg-accent", side: "bg-primary/10", bar: "bg-primary" },
  IN_PROGRESS: { label: "진행 중", badge: "primary", card: "bg-accent", side: "bg-primary/10", bar: "bg-primary" },
  COMPLETED: {
    label: "완료",
    badge: "success",
    card: "bg-success-subtle",
    side: "bg-success/10",
    bar: "bg-success",
  },
  NO_SHOW: {
    label: "노쇼",
    badge: "destructive",
    card: "bg-destructive-subtle",
    side: "bg-destructive/10",
    bar: "bg-destructive",
  },
  CANCELED: {
    label: "취소",
    badge: "warning",
    card: "bg-warning-subtle",
    side: "bg-warning/10",
    bar: "bg-warning",
  },
};

export function kindLabel(session: Pick<MentoringSession, "team_id" | "team_label">): string {
  return session.team_id ? `팀 멘토링 · ${session.team_label ?? "팀"}` : "1:1 멘토링";
}

/** 신청한 진행 시간(분) */
export function plannedMinutes(session: Pick<MentoringSession, "starts_at" | "ends_at">): number {
  return Math.round((toEpochMs(session.ends_at) - toEpochMs(session.starts_at)) / 60_000);
}

/** 실제 진행 분 (Meet 기록, A68). 시각이 없으면 null */
export function actualMinutes(session: Pick<MentoringSession, "actual_started_at" | "actual_ended_at">): number | null {
  if (!session.actual_started_at || !session.actual_ended_at) return null;
  return Math.round((toEpochMs(session.actual_ended_at) - toEpochMs(session.actual_started_at)) / 60_000);
}

export interface TimeBlock {
  label: "예약 일시" | "실제 진행";
  day: string;
  range: string;
  note: string;
}

/**
 * 카드 왼쪽 시각 (Figma `Screen / 진행 기록`).
 * 완료는 실제 진행(없으면 예약 일시)과 "59분 · 기록 60분", 그 밖은 예약 일시와 신청 분.
 */
export function timeBlock(session: MentoringSession): TimeBlock {
  const actual = actualMinutes(session);
  if (session.status === "COMPLETED" && session.actual_started_at && session.actual_ended_at && actual !== null) {
    const record = session.record_duration_minutes;
    return {
      label: "실제 진행",
      day: formatKstDay(session.actual_started_at),
      range: `${formatKst(session.actual_started_at, "HH:mm")} ~ ${formatKst(session.actual_ended_at, "HH:mm")}`,
      note: record === null ? `${actual}분` : `${actual}분 · 기록 ${record}분`,
    };
  }
  const record = session.status === "COMPLETED" ? session.record_duration_minutes : null;
  return {
    label: "예약 일시",
    day: formatKstDay(session.starts_at),
    range: `${formatKst(session.starts_at, "HH:mm")} ~ ${formatKst(session.ends_at, "HH:mm")}`,
    note: record === null ? `${plannedMinutes(session)}분` : `기록 ${record}분`,
  };
}

/** "11/16(월) 10:00 ~ 11:00" */
export function scheduleLabel(session: Pick<MentoringSession, "starts_at" | "ends_at">): string {
  return `${formatKstDay(session.starts_at)} ${formatKst(session.starts_at, "HH:mm")} ~ ${formatKst(session.ends_at, "HH:mm")}`;
}

/**
 * 진행 시간 칸 아래 줄 (balance, A66·A68).
 * 차감됨이면 신청 시간과 비교해 추가 차감·돌려받음을 덧붙인다 (A53 REFUND·OVERTIME).
 */
export function balanceNote(session: MentoringSession): string | null {
  const { state, minutes } = session.balance;
  const team = session.team_id ? "팀 계좌 " : "";
  switch (state) {
    case "HELD":
      return `${team}차감 예정 ${formatMinutes(minutes)}`;
    case "RETURNED":
      return "시간 돌려받음";
    case "NONE":
      return null;
    case "USED": {
      const planned = plannedMinutes(session);
      const base = `${team}${formatMinutes(minutes)} 차감`;
      if (session.status !== "COMPLETED") return base;
      if (minutes > planned) return `${base} · 추가 ${formatMinutes(minutes - planned)} 포함`;
      if (minutes < planned) return `${base} · ${formatMinutes(planned - minutes)} 돌려받음`;
      return `${base} · 추가 차감 없음`;
    }
  }
}

/** 노쇼 안내 (F33: 시안 문구 그대로) */
export const NO_SHOW_NOTE = "참석하지 않아 노쇼로 기록됐어요. 노쇼가 반복되면 멘토링 신청이 제한될 수 있어요";

/** "취소 사유 · 개인 일정 (11/05 08:10 본인 취소, 시간 돌려받음)" */
export function cancelNote(session: MentoringSession, mine: boolean): string | null {
  if (session.status !== "CANCELED") return null;
  const tail = [canceledTail(session, mine), session.balance.state === "RETURNED" ? "시간 돌려받음" : null]
    .filter(Boolean)
    .join(", ");
  const reason = session.cancel_reason ? `취소 사유 · ${session.cancel_reason}` : "취소된 세션이에요";
  return tail ? `${reason} (${tail})` : reason;
}

/** 내가 신청한 세션인지 (취소 주체 '본인' 표시) */
export function isMine(session: Pick<MentoringSession, "requester_id">, myStudentIds: Set<string>): boolean {
  return myStudentIds.has(session.requester_id);
}
