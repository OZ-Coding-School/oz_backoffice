import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { staffAccessQuery } from "@/features/staff/api";

export type Employee = components["schemas"]["EmployeeResponse"];
export type EmployeeAssignment = components["schemas"]["EmployeeAssignmentResponse"];
export type EmployeeUpdate = components["schemas"]["EmployeeUpdateRequest"];

export const employeeKeys = {
  all: ["admin-employees"] as const,
  list: () => ["admin-employees", "list"] as const,
};

/** 직원 전체, 담당·최고 관리자·데이터 범위 포함 (A83·A90·A91). 화면이 부서·팀별로 묶는다 */
export const employeesQuery = queryOptions({
  queryKey: employeeKeys.list(),
  queryFn: () => unwrap(api.GET("/api/v1/admin/employees")),
});

/** 소속·직위·담당·최고 관리자를 한 번에 저장 (A89·A90). 보낸 항목만 바뀐다 */
export function useUpdateEmployee(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: EmployeeUpdate) =>
      unwrap(api.PATCH("/api/v1/admin/employees/{employee_id}", { params: { path: { employee_id: id } }, body })),
    onSuccess: (saved) => {
      queryClient.setQueryData(employeeKeys.list(), (list: Employee[] | undefined) =>
        list?.map((e) => (e.id === saved.id ? saved : e)),
      );
      // 내 직위·담당·최고 관리자가 바뀌었을 수 있다
      void queryClient.invalidateQueries({ queryKey: staffAccessQuery.queryKey });
    },
  });
}

/** 담당 표시: '백엔드 부트캠프', '백엔드 부트캠프 12기' */
export function assignmentName(a: Pick<EmployeeAssignment, "bootcamp_name" | "cohort_number">): string {
  const name = a.bootcamp_name ?? "—";
  return a.cohort_number ? `${name} ${a.cohort_number}기` : name;
}

/** 목록의 담당 요약: 첫 대상과 '외 N' (없으면 '—') */
export function assignmentsSummary(items: readonly EmployeeAssignment[]): string {
  const [first, ...rest] = items;
  if (!first) return "—";
  return rest.length ? `${assignmentName(first)} 외 ${rest.length}` : assignmentName(first);
}

export const DATA_SCOPE_LABELS: Record<Employee["data_scope"], string> = {
  ASSIGNED: "담당 과정·기수만",
  ALL: "모든 과정·기수",
};
