import { infiniteQueryOptions, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type Applicant = components["schemas"]["ApplicantResponse"];
export type Candidates = components["schemas"]["CandidatesResponse"];
export type StudentCandidate = components["schemas"]["StudentCandidateResponse"];
export type ContractCandidate = components["schemas"]["ContractCandidateResponse"];
export type SignupType = components["schemas"]["MemberSignupType"];

export const PAGE_SIZE = 20;

/** 탭 (F60): 수강생·멘토. 주소 `?type=mentor` */
export type ApprovalTab = "student" | "mentor";

export function signupTypeOf(tab: ApprovalTab): SignupType {
  return tab === "mentor" ? "MENTOR" : "STUDENT";
}

export const approvalKeys = {
  all: ["admin-approvals"] as const,
  list: (tab: ApprovalTab, cohortId: string | undefined) =>
    ["admin-approvals", "list", tab, cohortId ?? "all"] as const,
  count: (type: SignupType | "all", cohortId: string | undefined) =>
    ["admin-approvals", "count", type, cohortId ?? "all"] as const,
  candidates: (userId: string, q: string) => ["admin-approvals", "candidates", userId, q] as const,
};

/** 승인 대기 (오래된 신청부터, 담당 범위만, A33). 20개씩 이어 붙인다 */
export function approvalsQuery(tab: ApprovalTab, cohortId: string | undefined) {
  return infiniteQueryOptions({
    queryKey: approvalKeys.list(tab, cohortId),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/admin/approvals", {
          params: {
            query: {
              signup_type: signupTypeOf(tab),
              limit: PAGE_SIZE,
              offset: pageParam,
              ...(cohortId && tab === "student" ? { cohort_id: cohortId } : {}),
            },
          },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
  });
}

/** 대기 건수 (탭 건수·메뉴 배지). 유형이 'all'이면 둘 다 */
export function approvalCountQuery(type: SignupType | "all", cohortId?: string) {
  return queryOptions({
    queryKey: approvalKeys.count(type, cohortId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/approvals", {
          params: {
            query: {
              limit: 1,
              offset: 0,
              ...(type === "all" ? {} : { signup_type: type }),
              ...(cohortId ? { cohort_id: cohortId } : {}),
            },
          },
        }),
      ),
    select: (page) => page.total,
  });
}

/** 수동 승인 후보 (A82). q가 없으면 이름 또는 휴대폰이 같은 것 */
export function candidatesQuery(userId: string, q: string) {
  return queryOptions({
    queryKey: approvalKeys.candidates(userId, q),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/approvals/{user_id}/candidates", {
          params: { path: { user_id: userId }, query: q ? { q } : {} },
        }),
      ),
  });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: approvalKeys.all });
}

/** 승인 (A33): 수강생은 명단 하나, 멘토는 계약 0개 이상 */
export function useApprove(userId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { student_id?: string; mentor_id?: string; contract_ids?: string[] }) =>
      unwrap(api.POST("/api/v1/admin/approvals/{user_id}/approve", { params: { path: { user_id: userId } }, body })),
    onSuccess: invalidate,
  });
}

/** 반려: 사유 필수 300자 (A33) */
export function useReject(userId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (reason: string) =>
      unwrap(
        api.POST("/api/v1/admin/approvals/{user_id}/reject", {
          params: { path: { user_id: userId } },
          body: { reason },
        }),
      ),
    onSuccess: invalidate,
  });
}
