import { http, HttpResponse } from "msw";

import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";

import type { ChatMessage, ChatThread } from "./api";

export function makeThread(overrides: Partial<ChatThread> = {}): ChatThread {
  return {
    id: "th1",
    kind: "DIRECT",
    cohort_id: "c12",
    student_id: "st12",
    student_name: "가수강",
    team_id: null,
    team_label: null,
    mentor_id: "m1",
    mentor_display_name: "멘토K",
    last_message_at: "2026-11-16T01:00:00Z",
    last_message: null,
    unread_count: 0,
    ...overrides,
  };
}

let seq = 0;
export function makeMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  seq += 1;
  return {
    id: `msg${seq}`,
    thread_id: "th1",
    sender_kind: "STUDENT",
    sender_id: "u1",
    sender_name: "가수강",
    body: `메시지 ${seq}`,
    is_deleted: false,
    created_at: "2026-11-15T00:20:00Z",
    ...overrides,
  };
}

/** 방 목록·단건·메시지(최신부터, before 커서)·보내기·삭제·읽음 */
export function mockChat(threads: ChatThread[], messages: Record<string, ChatMessage[]> = {}) {
  const calls = {
    read: [] as string[],
    sent: [] as string[],
    deleted: [] as string[],
    before: [] as (string | null)[],
  };
  const store = Object.fromEntries(Object.entries(messages).map(([k, v]) => [k, [...v]]));
  server.use(
    http.get(apiUrl("/api/v1/me/mentoring/chat/threads"), () =>
      HttpResponse.json({ items: threads, total: threads.length, limit: 50, offset: 0 }),
    ),
    http.get(apiUrl("/api/v1/mentoring/chat/threads/{thread_id}"), ({ params }) => {
      const t = threads.find((x) => x.id === params.thread_id);
      return t
        ? HttpResponse.json(t)
        : HttpResponse.json({ error: { code: "chat_thread_not_found", message: "없음" } }, { status: 404 });
    }),
    http.get(apiUrl("/api/v1/mentoring/chat/threads/{thread_id}/messages"), ({ params, request }) => {
      const url = new URL(request.url);
      const before = url.searchParams.get("before");
      const limit = Number(url.searchParams.get("limit") ?? 50);
      calls.before.push(before);
      const all = [...(store[String(params.thread_id)] ?? [])].reverse(); // 최신부터
      const start = before ? all.findIndex((m) => m.id === before) + 1 : 0;
      const items = all.slice(start, start + limit);
      const next = start + limit < all.length ? (items.at(-1)?.id ?? null) : null;
      return HttpResponse.json({ items, next_before: next });
    }),
    http.post(apiUrl("/api/v1/mentoring/chat/threads/{thread_id}/messages"), async ({ params, request }) => {
      const { body } = (await request.json()) as { body: string };
      calls.sent.push(body);
      const m = makeMessage({ thread_id: String(params.thread_id), body, created_at: "2026-11-16T02:00:00Z" });
      (store[String(params.thread_id)] ??= []).push(m);
      return HttpResponse.json(m, { status: 201 });
    }),
    http.delete(apiUrl("/api/v1/mentoring/chat/threads/{thread_id}/messages/{message_id}"), ({ params }) => {
      calls.deleted.push(String(params.message_id));
      const list = store[String(params.thread_id)] ?? [];
      const found = list.find((m) => m.id === params.message_id)!;
      Object.assign(found, { is_deleted: true, body: null });
      return HttpResponse.json(found);
    }),
    http.put(apiUrl("/api/v1/mentoring/chat/threads/{thread_id}/read"), async ({ params, request }) => {
      const { message_id } = (await request.json()) as { message_id: string };
      calls.read.push(message_id);
      const t = threads.find((x) => x.id === params.thread_id)!;
      return HttpResponse.json({ ...t, unread_count: 0 });
    }),
  );
  return calls;
}
