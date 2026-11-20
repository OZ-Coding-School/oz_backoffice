import type { Me } from "@/features/auth/api";
import { formatKst } from "@/lib/datetime";

import type { ChatMessage, ChatThread } from "./api";

/**
 * 방 이름 (F40): 수강생에게는 멘토(팀이면 '팀 · 멘토'), 멘토에게는 수강생·팀.
 * 멘토 화면의 아랫줄에는 1:1/팀을 붙인다.
 */
export function threadTitle(thread: ChatThread, viewer: Me["account_type"]): string {
  if (viewer === "MENTOR")
    return thread.kind === "TEAM" ? (thread.team_label ?? "팀") : (thread.student_name ?? "수강생");
  return thread.kind === "TEAM"
    ? `${thread.team_label ?? "팀"} · ${thread.mentor_display_name}`
    : thread.mentor_display_name;
}

export function threadKindLabel(thread: ChatThread): string {
  return thread.kind === "TEAM" ? "팀" : "1:1";
}

/** 목록 미리보기. 팀 방은 보낸 사람을 앞에 붙인다(시안) */
export function preview(thread: Pick<ChatThread, "kind" | "last_message">): string {
  const message = thread.last_message;
  if (!message) return "아직 메시지가 없어요";
  if (message.is_deleted) return "삭제된 메시지입니다.";
  const body = message.body ?? "";
  if (thread.kind !== "TEAM" || message.sender_kind === "SYSTEM" || !message.sender_name) return body;
  return `${message.sender_name}: ${body}`;
}

export function isMine(message: ChatMessage, me: Pick<Me, "id">): boolean {
  return message.sender_id === me.id;
}

/** "11/15 09:20" */
export function messageTime(message: Pick<ChatMessage, "created_at">): string {
  return formatKst(message.created_at, "MM/dd HH:mm");
}
