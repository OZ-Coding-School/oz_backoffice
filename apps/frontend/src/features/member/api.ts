import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type Enrollment = components["schemas"]["EnrollmentResponse"];
export type EnrollmentStatus = components["schemas"]["EnrollmentStatus"];

export const memberKeys = {
  enrollments: ["member", "enrollments"] as const,
};

/** 내 수강 등록 (상태 무관 전부, 기수 시작일이 늦은 것부터, A64) */
export const enrollmentsQuery = queryOptions({
  queryKey: memberKeys.enrollments,
  queryFn: () => unwrap(api.GET("/api/v1/me/enrollments")),
  staleTime: 5 * 60_000,
});

export interface ActiveCohort {
  enrollment: Enrollment;
  /** 수강이 끝났으면 지난 기록만 볼 수 있다 (새 신청 불가, F27) */
  readOnly: boolean;
}

/**
 * 활성 기수 (F27): 수강 중(ENROLLED) 등록. KDT는 동시 수강이 없어 하나뿐이다.
 * 화면은 기수로 제한하지 않고, 기수가 필요한 요청(신청·설정 요약·멘토 목록)에만 이 기수를 넣어 보낸다.
 * 수강 중이 없으면 가장 최근 기수를 읽기 전용으로 쓴다(새 신청 불가). 등록이 없으면 null.
 */
export function activeCohort(enrollments: readonly Enrollment[]): ActiveCohort | null {
  const byLatest = [...enrollments].sort((a, b) => b.start_date.localeCompare(a.start_date));
  const enrolled = byLatest.find((e) => e.status === "ENROLLED");
  if (enrolled) return { enrollment: enrolled, readOnly: false };
  const latest = byLatest[0];
  return latest ? { enrollment: latest, readOnly: true } : null;
}

export const ENROLLMENT_STATUS_LABELS: Record<EnrollmentStatus, string> = {
  ENROLLED: "수강 중",
  COMPLETED: "수료",
  DROPPED: "중도포기",
  EARLY_EMPLOYED: "조기취업",
  TRANSFERRED: "기수 이동",
};

export function cohortLabel(e: Pick<Enrollment, "bootcamp_name" | "cohort_number">): string {
  return `${e.bootcamp_name} ${e.cohort_number}기`;
}
