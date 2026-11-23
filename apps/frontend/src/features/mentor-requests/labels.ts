import type { BadgeProps } from "@/components/ui/badge";
import type { MentoringRequest, RequestStatus } from "@/features/requests/api";
import { formatKst, formatKstDay } from "@/lib/datetime";

type Tone = NonNullable<BadgeProps["variant"]>;

/** 멘토 화면 상태 배지 (Figma `받은 신청`: 대기·승인·반려) */
export const RECEIVED_STATUS: Record<RequestStatus, { label: string; badge: Tone }> = {
  PENDING: { label: "대기", badge: "warning" },
  APPROVED: { label: "승인", badge: "success" },
  REJECTED: { label: "반려", badge: "destructive" },
  CANCELED: { label: "취소", badge: "secondary" },
};

/** "11/24(화) 19:00" */
function dayTime(iso: string): string {
  return `${formatKstDay(iso)} ${formatKst(iso, "HH:mm")}`;
}

/**
 * 희망 일시 칸 (F43): 대기는 첫 희망 일시와 '외 N', 승인은 확정 일시, 반려·취소는 '—'.
 */
export function desiredLabel(request: Pick<MentoringRequest, "status" | "desired_times" | "session">): string {
  if (request.status === "APPROVED") return request.session ? dayTime(request.session.starts_at) : "—";
  if (request.status !== "PENDING") return "—";
  const [first, ...rest] = [...request.desired_times].sort();
  if (!first) return "—";
  return rest.length ? `${dayTime(first)} 외 ${rest.length}` : dayTime(first);
}

/** "가수강 · 1:1" / "3팀 알파 · 팀" */
export function requesterLabel(request: Pick<MentoringRequest, "team_id" | "team_label" | "requester_name">): string {
  return request.team_id ? `${request.team_label ?? "팀"} · 팀` : `${request.requester_name} · 1:1`;
}

/** "60분 · 백엔드 12기" */
export function metaLabel(request: Pick<MentoringRequest, "duration" | "bootcamp_name" | "cohort_number">): string {
  const cohort =
    request.bootcamp_name && request.cohort_number ? `${request.bootcamp_name} ${request.cohort_number}기` : null;
  return [`${request.duration}분`, cohort].filter(Boolean).join(" · ");
}

/** "11/16 10:02" */
export function requestedAt(request: Pick<MentoringRequest, "created_at">): string {
  return request.created_at ? formatKst(request.created_at, "MM/dd HH:mm") : "—";
}
