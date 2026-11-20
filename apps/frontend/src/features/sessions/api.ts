import { infiniteQueryOptions, queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { env } from "@/env";

export type MentoringSession = components["schemas"]["SessionResponse"];
export type SessionStatus = components["schemas"]["MentoringSessionStatus"];
export type SessionCounts = components["schemas"]["SessionStatusCounts"];

export const PAGE_SIZE = 20;

/** 목록 탭 (F33·A70): 예정 탭은 예정과 진행 중을 함께 보여 준다 */
export const SESSION_TABS = [
  { value: "all", label: "전체", statuses: [] },
  { value: "scheduled", label: "예정", statuses: ["SCHEDULED", "IN_PROGRESS"] },
  { value: "completed", label: "완료", statuses: ["COMPLETED"] },
  { value: "canceled", label: "취소", statuses: ["CANCELED"] },
  { value: "no_show", label: "노쇼", statuses: ["NO_SHOW"] },
] as const satisfies readonly { value: string; label: string; statuses: readonly SessionStatus[] }[];

export type SessionTab = (typeof SESSION_TABS)[number]["value"];

const ALL_STATUSES: readonly SessionStatus[] = ["SCHEDULED", "IN_PROGRESS", "COMPLETED", "NO_SHOW", "CANCELED"];

/** 탭 건수: counts는 필터와 무관한 전체 기준이다 (A68) */
export function tabCount(tab: SessionTab, counts: SessionCounts): number {
  const def = SESSION_TABS.find((t) => t.value === tab);
  const statuses: readonly SessionStatus[] = def?.statuses.length ? def.statuses : ALL_STATUSES;
  return statuses.reduce((sum, s) => sum + counts[s], 0);
}

export function isSessionTab(value: unknown): value is SessionTab {
  return SESSION_TABS.some((t) => t.value === value);
}

export const sessionKeys = {
  all: ["sessions"] as const,
  list: (tab: SessionTab) => ["sessions", "mine", tab] as const,
  detail: (id: string) => ["sessions", "detail", id] as const,
};

/** 내 세션 목록 (본인 1:1 + 소속 팀, 20개씩 이어 붙인다, F33) */
export function mySessionsQuery(tab: SessionTab) {
  const statuses = [...(SESSION_TABS.find((t) => t.value === tab)?.statuses ?? [])];
  return infiniteQueryOptions({
    queryKey: sessionKeys.list(tab),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/me/mentoring/sessions", {
          params: {
            query: { limit: PAGE_SIZE, offset: pageParam, ...(statuses.length ? { status: statuses } : {}) },
          },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
  });
}

/** 세션 단건 (참여자·담당 멘토만, 아니면 404) */
export function sessionQuery(id: string) {
  return queryOptions({
    queryKey: sessionKeys.detail(id),
    queryFn: () => unwrap(api.GET("/api/v1/mentoring/sessions/{session_id}", { params: { path: { session_id: id } } })),
  });
}

export type Artifact = components["schemas"]["ArtifactResponse"];
export type TranscriptEntry = components["schemas"]["TranscriptEntryResponse"];

export const artifactKeys = {
  list: (sessionId: string) => ["sessions", "artifacts", sessionId] as const,
  link: (artifactId: string) => ["sessions", "artifact-link", artifactId] as const,
  entries: (artifactId: string) => ["sessions", "artifact-entries", artifactId] as const,
  markdown: (artifactId: string) => ["sessions", "artifact-markdown", artifactId] as const,
};

/** 세션의 녹화·전사본·스마트 메모 (참여자만, A54) */
export function artifactsQuery(sessionId: string) {
  return queryOptions({
    queryKey: artifactKeys.list(sessionId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/mentoring/sessions/{session_id}/artifacts", { params: { path: { session_id: sessionId } } }),
      ),
  });
}

/** 링크 유효 3시간(A68) — 만료 전에 새로 받도록 2시간 30분 동안만 쓴다 */
const LINK_STALE_MS = 150 * 60_000;

/**
 * 서명 링크 (A68): 헤더 없이 `<video src>`·내려받기·PDF 새 창에 쓴다.
 * 응답은 API 기준 경로라 백엔드 주소를 붙인다.
 */
export function artifactLinkQuery(sessionId: string, artifactId: string) {
  return queryOptions({
    queryKey: artifactKeys.link(artifactId),
    queryFn: async () => {
      const link = await unwrap(
        api.POST("/api/v1/mentoring/sessions/{session_id}/artifacts/{artifact_id}/link", {
          params: { path: { session_id: sessionId, artifact_id: artifactId } },
        }),
      );
      return { ...link, url: env.backendUrl + link.url, download_url: env.backendUrl + link.download_url };
    },
    staleTime: LINK_STALE_MS,
    gcTime: LINK_STALE_MS,
  });
}

/** 전사 문장 (A69). 아직 못 받았으면 빈 목록 */
export function transcriptEntriesQuery(sessionId: string, artifactId: string) {
  return queryOptions({
    queryKey: artifactKeys.entries(artifactId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/mentoring/sessions/{session_id}/artifacts/{artifact_id}/entries", {
          params: { path: { session_id: sessionId, artifact_id: artifactId } },
        }),
      ),
  });
}

/** 스마트 메모 마크다운 (A68) */
export function summaryMarkdownQuery(sessionId: string, artifactId: string) {
  return queryOptions({
    queryKey: artifactKeys.markdown(artifactId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/mentoring/sessions/{session_id}/artifacts/{artifact_id}/markdown", {
          params: { path: { session_id: sessionId, artifact_id: artifactId } },
        }),
      ),
    staleTime: 10 * 60_000,
  });
}
