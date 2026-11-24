import { createFileRoute } from "@tanstack/react-router";

import { StaffPage, type StaffSearch } from "@/features/admin-staff/components/staff-page";
import { staffOptionsQuery } from "@/features/auth/staff-api";

function text(v: unknown): string | undefined {
  return typeof v === "string" && v ? v : undefined;
}

/** 직원·담당자 (F62). 탭 `tab=staff`, 직원 탭 `q`·`department`·`team`, 담당자 탭 `bootcamp`·`cohort` */
export const Route = createFileRoute("/_staff/admin/members/staff")({
  validateSearch: (search: Record<string, unknown>): StaffSearch => {
    const out: StaffSearch = {};
    if (search.tab === "staff") out.tab = "staff";
    for (const key of ["q", "department", "team", "bootcamp", "cohort"] as const) {
      const v = text(search[key]);
      if (v) out[key] = v;
    }
    return out;
  },
  loader: ({ context }) => context.queryClient.prefetchQuery(staffOptionsQuery),
  component: function Staff() {
    return <StaffPage search={Route.useSearch()} />;
  },
});
