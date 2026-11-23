import { infiniteQueryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

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
