import { createFileRoute } from "@tanstack/react-router";

import { registrationsQuery, type RegistrationTab } from "@/features/admin-staff-registrations/api";
import { RegistrationsPage } from "@/features/admin-staff-registrations/components/registrations-page";
import { staffOptionsQuery } from "@/features/auth/staff-api";

interface RegistrationsSearch {
  status?: Exclude<RegistrationTab, "pending">;
}

/** 운영진 승인 (F61). 탭 `status`(기본 대기) */
export const Route = createFileRoute("/_staff/admin/members/staff-registrations")({
  validateSearch: (search: Record<string, unknown>): RegistrationsSearch =>
    search.status === "approved" || search.status === "rejected" ? { status: search.status } : {},
  loaderDeps: ({ search }): { tab: RegistrationTab } => ({ tab: search.status ?? "pending" }),
  loader: ({ context, deps }) =>
    Promise.all([
      context.queryClient.prefetchInfiniteQuery(registrationsQuery(deps.tab)),
      context.queryClient.prefetchQuery(staffOptionsQuery),
    ]),
  component: function StaffRegistrations() {
    const { status } = Route.useSearch();
    return <RegistrationsPage tab={status ?? "pending"} />;
  },
});
