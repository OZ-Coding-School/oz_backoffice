import { createFileRoute } from "@tanstack/react-router";

import { departmentsQuery, teamsQuery } from "@/features/admin-org/api";
import { DepartmentsPage, type DepartmentsSearch } from "@/features/admin-org/components/departments-page";
import { staffOptionsQuery } from "@/features/auth/staff-api";

const text = (v: unknown) => (typeof v === "string" && v ? v : undefined);

/** 조직 설정 > 부서 (F69). 보기 `view=tree`(기본 목록), 패널 `department` 또는 `team` */
export const Route = createFileRoute("/_staff/admin/org/departments")({
  validateSearch: (search: Record<string, unknown>): DepartmentsSearch => {
    const out: DepartmentsSearch = {};
    if (search.view === "tree") out.view = "tree";
    const department = text(search.department);
    const team = text(search.team);
    if (department) out.department = department;
    else if (team) out.team = team;
    return out;
  },
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.prefetchQuery(departmentsQuery),
      context.queryClient.prefetchQuery(teamsQuery),
      context.queryClient.prefetchQuery(staffOptionsQuery),
    ]),
  component: function Departments() {
    return <DepartmentsPage search={Route.useSearch()} />;
  },
});
