import { infiniteQueryOptions, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { sessionKeys, type MentoringSession } from "@/features/sessions/api";

export type SessionViewCounts = components["schemas"]["SessionViewCounts"];

export const PAGE_SIZE = 20;

/** 목록 탭 (F46·A77): 다가오는이 기본이고 이른 순, 그 밖은 최신순 */
export const MENTOR_SESSION_TABS = [
  { value: "upcoming", label: "다가오는", view: "upcoming", ascending: true },
  { value: "record_missing", label: "기록 미제출", view: "record_missing", ascending: false },
  { value: "past", label: "지난 세션", view: "past", ascending: false },
  { value: "all", label: "전체", view: null, ascending: false },
] as const;

export type MentorSessionTab = (typeof MENTOR_SESSION_TABS)[number]["value"];

export function isMentorSessionTab(value: unknown): value is MentorSessionTab {
  return MENTOR_SESSION_TABS.some((t) => t.value === value);
}

export const mentorSessionKeys = {
  all: ["sessions", "mentor"] as const,
  list: (tab: MentorSessionTab, cohortId: string | undefined) =>
    ["sessions", "mentor", "list", tab, cohortId ?? "all"] as const,
};

/** 멘토 세션 (20개씩 이어 붙인다, 탭·기수 필터 A77) */
export function mentorSessionsQuery(tab: MentorSessionTab, cohortId: string | undefined) {
  const def = MENTOR_SESSION_TABS.find((t) => t.value === tab) ?? MENTOR_SESSION_TABS[0];
  return infiniteQueryOptions({
    queryKey: mentorSessionKeys.list(tab, cohortId),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/me/mentor-sessions", {
          params: {
            query: {
              limit: PAGE_SIZE,
              offset: pageParam,
              ...(def.view ? { view: def.view } : {}),
              ...(def.ascending ? { order: "asc" as const } : {}),
              ...(cohortId ? { cohort_id: cohortId } : {}),
            },
          },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
  });
}

export type RecordBody = components["schemas"]["RecordBody"];
export type SessionNote = components["schemas"]["NoteResponse"];

/** 기록 제출·수정 뒤: 응답으로 상세 캐시를 고치고 세션 목록(멘토·수강생)을 다시 부른다 */
function useApplySession(id: string) {
  const queryClient = useQueryClient();
  return (session: MentoringSession) => {
    queryClient.setQueryData(sessionKeys.detail(id), session);
    // 목록(멘토·수강생·팀·홈)만 다시 부른다. 상세·메모·녹화는 그대로
    void queryClient.invalidateQueries({
      queryKey: ["sessions"],
      predicate: (q) => ["mine", "mentor", "team"].includes(String(q.queryKey[1])),
    });
  };
}

/** 기록 제출 (A53·A78): 완료(진행 시간·주제·요약) 또는 노쇼(사유 선택). 결과·진행 시간은 처음 제출로 고정 */
export function useSubmitRecord(id: string) {
  const apply = useApplySession(id);
  return useMutation({
    mutationFn: (body: RecordBody) =>
      unwrap(
        api.POST("/api/v1/mentoring/sessions/{session_id}/record", { params: { path: { session_id: id } }, body }),
      ),
    onSuccess: apply,
  });
}

/** 기록 수정: 주제·요약만, 제출 후 7일까지 (A53) */
export function useEditRecord(id: string) {
  const apply = useApplySession(id);
  return useMutation({
    mutationFn: (body: { topic: string; summary: string }) =>
      unwrap(
        api.PATCH("/api/v1/mentoring/sessions/{session_id}/record", { params: { path: { session_id: id } }, body }),
      ),
    onSuccess: apply,
  });
}

export const noteKeys = { detail: (id: string) => ["sessions", "note", id] as const };

/** 내부 메모 (담당 멘토 작성, 운영진도 본다. 수강생은 못 본다) */
export function noteQuery(id: string) {
  return queryOptions({
    queryKey: noteKeys.detail(id),
    queryFn: () =>
      unwrap(api.GET("/api/v1/mentoring/sessions/{session_id}/note", { params: { path: { session_id: id } } })),
  });
}

export function useSaveNote(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) =>
      unwrap(
        api.PUT("/api/v1/mentoring/sessions/{session_id}/note", {
          params: { path: { session_id: id } },
          body: { body },
        }),
      ),
    onSuccess: (note) => queryClient.setQueryData(noteKeys.detail(id), note),
  });
}
