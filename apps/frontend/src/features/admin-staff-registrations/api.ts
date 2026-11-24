import { infiniteQueryOptions, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import type { StaffOptions } from "@/features/auth/staff-api";
import type { StaffCohort } from "@/features/staff/api";

export type AdminRegistration = components["schemas"]["AdminStaffRegistrationResponse"];
export type ApproveRegistrationBody = components["schemas"]["ApproveStaffRegistrationRequest"];
export type RegistrationStatus = components["schemas"]["EmployeeRegistrationStatus"];

export const PAGE_SIZE = 20;

/** 탭 (F61): 대기·승인·반려. 주소 `?status=approved|rejected` */
export type RegistrationTab = "pending" | "approved" | "rejected";

export const REGISTRATION_TABS: { value: RegistrationTab; label: string; status: RegistrationStatus }[] = [
  { value: "pending", label: "대기", status: "PENDING" },
  { value: "approved", label: "승인", status: "APPROVED" },
  { value: "rejected", label: "반려", status: "REJECTED" },
];

export const registrationKeys = {
  all: ["admin-staff-registrations"] as const,
  list: (tab: RegistrationTab) => ["admin-staff-registrations", "list", tab] as const,
  pending: ["admin-staff-registrations", "pending-count"] as const,
};

function statusOf(tab: RegistrationTab): RegistrationStatus {
  return REGISTRATION_TABS.find((t) => t.value === tab)?.status ?? "PENDING";
}

/** 운영진 가입 신청 (role.assign, A12). 20개씩 이어 붙인다 */
export function registrationsQuery(tab: RegistrationTab) {
  return infiniteQueryOptions({
    queryKey: registrationKeys.list(tab),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/admin/staff-registrations", {
          params: { query: { status: statusOf(tab), limit: PAGE_SIZE, offset: pageParam } },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
  });
}

/** 대기 건수 (탭·메뉴 배지) */
export const pendingRegistrationsQuery = queryOptions({
  queryKey: registrationKeys.pending,
  queryFn: () =>
    unwrap(
      api.GET("/api/v1/admin/staff-registrations", { params: { query: { status: "PENDING", limit: 1, offset: 0 } } }),
    ),
  select: (page) => page.total,
});

function useInvalidate() {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: registrationKeys.all });
}

/** 승인 (A11·A62): 고친 값으로 직원·담당자를 만든다 */
export function useApproveRegistration(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: ApproveRegistrationBody) =>
      unwrap(
        api.POST("/api/v1/admin/staff-registrations/{registration_id}/approve", {
          params: { path: { registration_id: id } },
          body,
        }),
      ),
    onSuccess: invalidate,
  });
}

/** 반려: 사유 필수 300자 */
export function useRejectRegistration(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (reason: string) =>
      unwrap(
        api.POST("/api/v1/admin/staff-registrations/{registration_id}/reject", {
          params: { path: { registration_id: id } },
          body: { reason },
        }),
      ),
    onSuccess: invalidate,
  });
}

type CohortOption = StaffOptions["cohorts"][number];

function asOption(c: StaffCohort): CohortOption {
  return {
    id: c.id,
    bootcamp_id: c.bootcamp_id,
    cohort_number: c.cohort_number,
    status: c.status as CohortOption["status"],
    start_date: c.start_date,
    end_date: c.end_date,
  };
}

/**
 * 이름표·넓게 보기에 쓰는 선택지: 신청 선택지의 기수(조교 없는 기수만)에 담당 기수(A81)를 더한다.
 * 이미 조교가 있거나 끝난 기수의 이름도 보이게 하려는 것이다
 */
export function withAllCohorts(options: StaffOptions, cohorts: readonly StaffCohort[]): StaffOptions {
  const known = new Set(options.cohorts.map((c) => c.id));
  return { ...options, cohorts: [...options.cohorts, ...cohorts.filter((c) => !known.has(c.id)).map(asOption)] };
}

/** 넓게 볼 때 기수: 진행 예정·진행 중 (A62 승인 조정 자유) */
export function openCohorts(cohorts: readonly StaffCohort[]): CohortOption[] {
  return cohorts.filter((c) => c.status === "PLANNED" || c.status === "ONGOING").map(asOption);
}
