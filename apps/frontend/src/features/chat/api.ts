import {
  infiniteQueryOptions,
  queryOptions,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type ChatThread = components["schemas"]["ThreadResponse"];
export type ChatMessage = components["schemas"]["MessageResponse"];
export type MessagePage = components["schemas"]["MessagePage"];
type ThreadPage = components["schemas"]["Page_ThreadResponse_"];

export const THREAD_PAGE_SIZE = 50;
export const MESSAGE_PAGE_SIZE = 50;
/** 메시지 길이 (A57: 텍스트 2,000자) */
export const MESSAGE_MAX_LENGTH = 2000;

export const chatKeys = {
  threads: ["chat", "threads"] as const,
  thread: (id: string) => ["chat", "thread", id] as const,
  messages: (id: string) => ["chat", "messages", id] as const,
};

/** 내 방 목록 (마지막 메시지 최신순, 안 읽음 수, A57). 50개씩 이어 붙인다 */
export const threadsQuery = infiniteQueryOptions({
  queryKey: chatKeys.threads,
  initialPageParam: 0,
  queryFn: ({ pageParam }) =>
    unwrap(
      api.GET("/api/v1/me/mentoring/chat/threads", {
        params: { query: { limit: THREAD_PAGE_SIZE, offset: pageParam } },
      }),
    ),
  getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
});

export function threadQuery(id: string) {
  return queryOptions({
    queryKey: chatKeys.thread(id),
    queryFn: () =>
      unwrap(api.GET("/api/v1/mentoring/chat/threads/{thread_id}", { params: { path: { thread_id: id } } })),
  });
}

/** 메시지 (최신부터 50개, 위로 올리면 before 커서로 이전 50개, A57) */
export function messagesQuery(id: string) {
  return infiniteQueryOptions({
    queryKey: chatKeys.messages(id),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/mentoring/chat/threads/{thread_id}/messages", {
          params: {
            path: { thread_id: id },
            query: { limit: MESSAGE_PAGE_SIZE, ...(pageParam ? { before: pageParam } : {}) },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_before ?? undefined,
  });
}

/** 화면에 보일 순서(오래된 것 → 최신)로 펼친다. 페이지는 최신부터 온다 */
export function chronological(data: InfiniteData<MessagePage> | undefined): ChatMessage[] {
  return (data?.pages ?? []).flatMap((p) => p.items).toReversed();
}

type MessagesData = InfiniteData<MessagePage, string | null>;

function upsertMessage(data: MessagesData | undefined, message: ChatMessage): MessagesData | undefined {
  if (!data) return data;
  const exists = data.pages.some((p) => p.items.some((m) => m.id === message.id));
  if (exists) {
    return {
      ...data,
      pages: data.pages.map((p) => ({ ...p, items: p.items.map((m) => (m.id === message.id ? message : m)) })),
    };
  }
  const [first, ...rest] = data.pages;
  if (!first) return data;
  return { ...data, pages: [{ ...first, items: [message, ...first.items] }, ...rest] };
}

/** 받거나 보낸 메시지를 캐시에 넣는다 (실시간 수신 FE-7b도 같이 쓴다) */
export function useApplyMessage() {
  const queryClient = useQueryClient();
  return (message: ChatMessage) => {
    queryClient.setQueryData<MessagesData>(chatKeys.messages(message.thread_id), (data) =>
      upsertMessage(data, message),
    );
    // 안 읽음 수가 바뀌므로 목록과 그 방을 다시 본다
    void queryClient.invalidateQueries({ queryKey: chatKeys.threads });
    void queryClient.invalidateQueries({ queryKey: chatKeys.thread(message.thread_id) });
  };
}

/** 방 상태(안 읽음 등)를 방 단건·목록 캐시에 반영한다 (읽음, 실시간 `read`) */
export function useApplyThread() {
  const queryClient = useQueryClient();
  return (thread: ChatThread) => {
    queryClient.setQueryData(chatKeys.thread(thread.id), thread);
    queryClient.setQueryData<InfiniteData<ThreadPage, number>>(chatKeys.threads, (data) =>
      data
        ? {
            ...data,
            pages: data.pages.map((p) => ({ ...p, items: p.items.map((t) => (t.id === thread.id ? thread : t)) })),
          }
        : data,
    );
  };
}

/** 안 읽음 합 (메뉴 배지, F41) */
export function unreadTotal(data: InfiniteData<ThreadPage> | undefined): number {
  return (data?.pages ?? []).reduce((sum, p) => sum + p.items.reduce((s, t) => s + t.unread_count, 0), 0);
}

/** 상대와의 방 찾기 (F41): 세션·내 팀의 [채팅]. 팀이면 팀-멘토, 아니면 수강 등록-멘토 1:1 */
export function findThread(
  data: InfiniteData<ThreadPage> | undefined,
  target: { mentorId: string; teamId?: string | null; studentId?: string | null },
): ChatThread | undefined {
  return (data?.pages ?? [])
    .flatMap((p) => p.items)
    .find((t) =>
      t.mentor_id !== target.mentorId
        ? false
        : target.teamId
          ? t.kind === "TEAM" && t.team_id === target.teamId
          : t.kind === "DIRECT" && t.student_id === target.studentId,
    );
}

export function useSendMessage(threadId: string) {
  const apply = useApplyMessage();
  return useMutation({
    mutationFn: (body: string) =>
      unwrap(
        api.POST("/api/v1/mentoring/chat/threads/{thread_id}/messages", {
          params: { path: { thread_id: threadId } },
          body: { body },
        }),
      ),
    onSuccess: apply,
  });
}

export function useDeleteMessage(threadId: string) {
  const apply = useApplyMessage();
  return useMutation({
    mutationFn: (messageId: string) =>
      unwrap(
        api.DELETE("/api/v1/mentoring/chat/threads/{thread_id}/messages/{message_id}", {
          params: { path: { thread_id: threadId, message_id: messageId } },
        }),
      ),
    onSuccess: apply,
  });
}

/** 본 마지막 메시지까지 읽음 (앞으로만 옮긴다, A57) */
export function useMarkRead(threadId: string) {
  const applyThread = useApplyThread();
  return useMutation({
    mutationFn: (messageId: string) =>
      unwrap(
        api.PUT("/api/v1/mentoring/chat/threads/{thread_id}/read", {
          params: { path: { thread_id: threadId } },
          body: { message_id: messageId },
        }),
      ),
    onSuccess: applyThread,
  });
}
