import { createFileRoute } from "@tanstack/react-router";

import { employeesQuery } from "@/features/admin-employees/api";
import { EmployeesPage } from "@/features/admin-employees/components/employees-page";
import { staffOptionsQuery } from "@/features/auth/staff-api";

export interface EmployeesSearch {
  employee?: string;
}

/** 조직 설정 > 직원 (F67). 패널로 연 직원 `employee` */
export const Route = createFileRoute("/_staff/admin/org/employees")({
  validateSearch: (search: Record<string, unknown>): EmployeesSearch =>
    typeof search.employee === "string" && search.employee ? { employee: search.employee } : {},
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.prefetchQuery(employeesQuery),
      context.queryClient.prefetchQuery(staffOptionsQuery),
    ]),
  component: function Employees() {
    return <EmployeesPage employeeId={Route.useSearch().employee} />;
  },
});
