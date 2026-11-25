import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type RosterStudent = components["schemas"]["RosterStudentResponse"];
export type StudentDetail = components["schemas"]["StudentDetailResponse"];
export type EnrollmentStatus = RosterStudent["status"];
export type AdminRequest = components["schemas"]["AdminRequestResponse"];
export type AdminSession = components["schemas"]["AdminSessionResponse"];

export const studentKeys = {
  all: ["admin-students"] as const,
  roster: (cohortId: string) => ["admin-students", "roster", cohortId] as const,
  detail: (cohortId: string, studentId: string) => ["admin-students", "detail", cohortId, studentId] as const,
  recent: (cohortId: string, studentId: string) => ["admin-students", "recent", cohortId, studentId] as const,
};

/** 기수 명단 (원본에서 빠진 행 제외, 이름순) */
export function rosterQuery(cohortId: string) {
  return queryOptions({
    queryKey: studentKeys.roster(cohortId),
    queryFn: () =>
      unwrap(api.GET("/api/v1/admin/cohorts/{cohort_id}/rosters", { params: { path: { cohort_id: cohortId } } })),
  });
}

/** 기본·수강 + 가입 계정 + 멘토링 요약 (A99) */
export function studentQuery(cohortId: string, studentId: string) {
  return queryOptions({
    queryKey: studentKeys.detail(cohortId, studentId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/cohorts/{cohort_id}/students/{student_id}", {
          params: { path: { cohort_id: cohortId, student_id: studentId } },
        }),
      ),
  });
}

export type RecentItem =
  { kind: "request"; at: string; request: AdminRequest } | { kind: "session"; at: string; session: AdminSession };

/** 최근 신청·세션 3건 (F76): 대기 신청과 세션을 합쳐 최근 순 */
export function recentQuery(cohortId: string, studentId: string) {
  return queryOptions({
    queryKey: studentKeys.recent(cohortId, studentId),
    queryFn: async (): Promise<RecentItem[]> => {
      const path = { cohort_id: cohortId };
      const [requests, sessions] = await Promise.all([
        unwrap(
          api.GET("/api/v1/admin/cohorts/{cohort_id}/mentoring/requests", {
            params: { path, query: { student_id: studentId, status: "PENDING", limit: 3 } },
          }),
        ),
        unwrap(
          api.GET("/api/v1/admin/cohorts/{cohort_id}/mentoring/sessions", {
            params: { path, query: { student_id: studentId, limit: 3 } },
          }),
        ),
      ]);
      const items: RecentItem[] = [
        ...requests.items.map((r) => ({
          kind: "request" as const,
          at: [...r.desired_times].sort()[0] ?? r.created_at ?? "",
          request: r,
        })),
        ...sessions.items.map((s) => ({ kind: "session" as const, at: s.starts_at, session: s })),
      ];
      return items.sort((a, b) => b.at.localeCompare(a.at)).slice(0, 3);
    },
  });
}
