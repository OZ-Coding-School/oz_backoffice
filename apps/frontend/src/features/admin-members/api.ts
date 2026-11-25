import { infiniteQueryOptions, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type Member = components["schemas"]["MemberResponse"];
export type MemberDetail = components["schemas"]["MemberDetailResponse"];
export type AccountType = Member["account_type"];

export const PAGE_SIZE = 20;

/** 종류 탭 (F71). 주소 `?tab=` (없으면 전체) */
export type MemberTab = "student" | "mentor" | "staff";
export const TAB_TYPES: Record<MemberTab, AccountType> = { student: "STUDENT", mentor: "MENTOR", staff: "STAFF" };
export const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = { STUDENT: "수강생", MENTOR: "멘토", STAFF: "운영진" };

export interface MemberFilter {
  tab?: MemberTab;
  q?: string;
  status?: "active" | "inactive";
}

export const memberKeys = {
  all: ["admin-members"] as const,
  list: (f: MemberFilter) => ["admin-members", "list", f.tab ?? "", f.q ?? "", f.status ?? ""] as const,
  detail: (id: string) => ["admin-members", "detail", id] as const,
};

/** 승인된 계정 (A94). 20개씩 이어 붙인다 */
export function membersQuery(f: MemberFilter) {
  return infiniteQueryOptions({
    queryKey: memberKeys.list(f),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/admin/users", {
          params: {
            query: {
              limit: PAGE_SIZE,
              offset: pageParam,
              ...(f.tab ? { account_type: TAB_TYPES[f.tab] } : {}),
              ...(f.q ? { q: f.q } : {}),
              ...(f.status ? { status: f.status } : {}),
            },
          },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
  });
}

/** 계정 + 종류별 연결 정보 + 이력 */
export function memberQuery(id: string) {
  return queryOptions({
    queryKey: memberKeys.detail(id),
    queryFn: () => unwrap(api.GET("/api/v1/admin/users/{user_id}", { params: { path: { user_id: id } } })),
  });
}

/** 비활성화(사유 필수)·활성화(사유 선택). 응답으로 상세를 고치고 목록을 다시 읽는다 */
export function useSetActive(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ active, reason }: { active: boolean; reason: string }) =>
      active
        ? unwrap(
            api.POST("/api/v1/admin/users/{user_id}/activate", {
              params: { path: { user_id: id } },
              body: { reason: reason.trim() || null },
            }),
          )
        : unwrap(
            api.POST("/api/v1/admin/users/{user_id}/deactivate", {
              params: { path: { user_id: id } },
              body: { reason: reason.trim() },
            }),
          ),
    onSuccess: (detail) => {
      client.setQueryData(memberKeys.detail(id), detail);
      void client.invalidateQueries({ queryKey: ["admin-members", "list"] });
    },
  });
}

export const ENROLLMENT_LABELS: Record<string, string> = {
  ENROLLED: "수강 중",
  COMPLETED: "수료",
  DROPPED: "중도 포기",
  EARLY_EMPLOYED: "조기 취업",
  TRANSFERRED: "기수 이동",
};
