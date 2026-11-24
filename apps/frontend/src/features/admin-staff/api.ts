import { infiniteQueryOptions, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type Employee = components["schemas"]["EmployeeResponse"];
export type EmployeeAssignment = components["schemas"]["EmployeeAssignmentResponse"];
export type StaffMember = components["schemas"]["StaffMemberResponse"];
export type StaffRole = components["schemas"]["StaffRole"];
export type EmployeeUpdate = components["schemas"]["EmployeeUpdateRequest"];

export const PAGE_SIZE = 20;

/** 직원 탭 필터 (A83) */
export interface EmployeeFilter {
  q?: string;
  departmentId?: string;
  teamId?: string;
}

/** 담당 대상: 과정 또는 기수 (F62) */
export type StaffTarget = { kind: "bootcamp"; id: string } | { kind: "cohort"; id: string };

export const staffKeys = {
  all: ["admin-staff"] as const,
  employees: (f: EmployeeFilter) =>
    ["admin-staff", "employees", f.q ?? "", f.departmentId ?? "", f.teamId ?? ""] as const,
  search: (q: string) => ["admin-staff", "employee-search", q] as const,
  members: (t: StaffTarget) => ["admin-staff", "members", t.kind, t.id] as const,
};

/** 직원 목록 (담당 포함, A83). 20개씩 이어 붙인다 */
export function employeesQuery(f: EmployeeFilter) {
  return infiniteQueryOptions({
    queryKey: staffKeys.employees(f),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/admin/employees", {
          params: {
            query: {
              limit: PAGE_SIZE,
              offset: pageParam,
              ...(f.q ? { q: f.q } : {}),
              ...(f.departmentId ? { department_id: f.departmentId } : {}),
              ...(f.teamId ? { team_id: f.teamId } : {}),
            },
          },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
  });
}

/** 담당자 추가 창의 직원 찾기 (최대 20명) */
export function employeeSearchQuery(q: string) {
  return queryOptions({
    queryKey: staffKeys.search(q),
    queryFn: () =>
      unwrap(api.GET("/api/v1/admin/employees", { params: { query: { limit: 20, offset: 0, ...(q ? { q } : {}) } } })),
    select: (page) => page.items,
  });
}

/** 그 과정·기수의 담당자 */
export function staffMembersQuery(t: StaffTarget) {
  return queryOptions({
    queryKey: staffKeys.members(t),
    queryFn: () =>
      t.kind === "bootcamp"
        ? unwrap(api.GET("/api/v1/admin/bootcamps/{bootcamp_id}/staffs", { params: { path: { bootcamp_id: t.id } } }))
        : unwrap(api.GET("/api/v1/admin/cohorts/{cohort_id}/staffs", { params: { path: { cohort_id: t.id } } })),
  });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: staffKeys.all });
}

/** 담당자 추가 (staff.assign). 담당자가 바뀌면 그 직원의 역할도 바뀐다 (A17) */
export function useAddStaff(t: StaffTarget) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { employee_id: string; role: StaffRole }) =>
      t.kind === "bootcamp"
        ? unwrap(
            api.POST("/api/v1/admin/bootcamps/{bootcamp_id}/staffs", { params: { path: { bootcamp_id: t.id } }, body }),
          )
        : unwrap(api.POST("/api/v1/admin/cohorts/{cohort_id}/staffs", { params: { path: { cohort_id: t.id } }, body })),
    onSuccess: invalidate,
  });
}

export function useRemoveStaff(t: StaffTarget) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (staffId: string) =>
      t.kind === "bootcamp"
        ? unwrap(
            api.DELETE("/api/v1/admin/bootcamps/{bootcamp_id}/staffs/{staff_id}", {
              params: { path: { bootcamp_id: t.id, staff_id: staffId } },
            }),
          )
        : unwrap(
            api.DELETE("/api/v1/admin/cohorts/{cohort_id}/staffs/{staff_id}", {
              params: { path: { cohort_id: t.id, staff_id: staffId } },
            }),
          ),
    onSuccess: invalidate,
  });
}

/** 직원 소속 수정 (org.employee.manage) */
export function useUpdateEmployee(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: EmployeeUpdate) =>
      unwrap(api.PATCH("/api/v1/admin/employees/{employee_id}", { params: { path: { employee_id: id } }, body })),
    onSuccess: invalidate,
  });
}

/** 담당 표시: '백엔드 부트캠프', '백엔드 부트캠프 12기' */
export function assignmentName(a: Pick<EmployeeAssignment, "bootcamp_name" | "cohort_number">): string {
  const name = a.bootcamp_name ?? "—";
  return a.cohort_number ? `${name} ${a.cohort_number}기` : name;
}

/** 담당 요약: 첫 대상과 '외 N' (없으면 '없음') */
export function assignmentsSummary(items: readonly EmployeeAssignment[]): string {
  const [first, ...rest] = items;
  if (!first) return "없음";
  return rest.length ? `${assignmentName(first)} 외 ${rest.length}` : assignmentName(first);
}
