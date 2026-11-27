import type { BadgeProps } from "@/components/ui/badge";
import { isKstToday } from "@/features/home/api";
import type { MentoringSession } from "@/features/sessions/api";
import { plannedMinutes } from "@/features/sessions/labels";
import { formatKst, formatKstDay, toEpochMs } from "@/lib/datetime";

type Tone = NonNullable<BadgeProps["variant"]>;

function open(session: Pick<MentoringSession, "status">): boolean {
  return session.status === "SCHEDULED" || session.status === "IN_PROGRESS";
}

/**
 * 멘토 화면 상태 배지 (F47): 오늘·예정·진행 중·진행됨(끝 시각이 지났는데 기록 전)·완료·노쇼·취소.
 */
export function mentorStatus(
  session: Pick<MentoringSession, "status" | "starts_at" | "ends_at">,
  now: number,
): { label: string; badge: Tone } {
  switch (session.status) {
    case "COMPLETED":
      return { label: "완료", badge: "success" };
    case "NO_SHOW":
      return { label: "노쇼", badge: "destructive" };
    case "CANCELED":
      return { label: "취소", badge: "warning" };
  }
  if (toEpochMs(session.ends_at) <= now) return { label: "진행됨", badge: "secondary" };
  if (session.status === "IN_PROGRESS" || toEpochMs(session.starts_at) <= now)
    return { label: "진행 중", badge: "primary" };
  if (isKstToday(session.starts_at, now)) return { label: "오늘", badge: "info" };
  return { label: "예정", badge: "violet" };
}

/** 기록 칸 (F47): 제출했으면 'MM/DD 제출', 시작이 지났는데 없으면 미제출, 그 밖은 없음 */
export function recordState(
  session: Pick<MentoringSession, "status" | "starts_at" | "recorded_at">,
  now: number,
): { kind: "submitted"; label: string } | { kind: "missing" } | { kind: "none" } {
  if (session.recorded_at) return { kind: "submitted", label: `${formatKst(session.recorded_at, "MM/dd")} 제출` };
  if (open(session) && toEpochMs(session.starts_at) <= now) return { kind: "missing" };
  return { kind: "none" };
}

/** Meet 입장: 열린 세션이 오늘이거나 진행 중이고 아직 끝나지 않았으며 링크가 있을 때 */
export function canEnterMeet(
  session: Pick<MentoringSession, "status" | "starts_at" | "ends_at" | "google_meet_url">,
  now: number,
): boolean {
  return (
    open(session) &&
    !!session.google_meet_url &&
    toEpochMs(session.ends_at) > now &&
    (isKstToday(session.starts_at, now) || toEpochMs(session.starts_at) <= now)
  );
}

/** "11/20(금) 14:00" */
export function whenLabel(session: Pick<MentoringSession, "starts_at">): string {
  return `${formatKstDay(session.starts_at)} ${formatKst(session.starts_at, "HH:mm")}`;
}

/** 신청 시간, 완료면 "60분 → 90분" */
export function durationLabel(
  session: Pick<MentoringSession, "status" | "starts_at" | "ends_at" | "record_duration_minutes">,
): string {
  const planned = plannedMinutes(session);
  return session.status === "COMPLETED" && session.record_duration_minutes !== null
    ? `${planned}분 → ${session.record_duration_minutes}분`
    : `${planned}분`;
}

/** "가수강 · 1:1" / "3팀 알파 · 팀" */
export function targetLabel(session: Pick<MentoringSession, "team_id" | "team_label" | "requester_name">): string {
  return session.team_id ? `${session.team_label ?? "팀"} · 팀` : `${session.requester_name} · 1:1`;
}
