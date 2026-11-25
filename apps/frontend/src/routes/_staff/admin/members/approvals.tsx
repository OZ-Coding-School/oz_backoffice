import { createFileRoute } from "@tanstack/react-router";

import type { SignupTab } from "@/features/admin-approvals/tabs";
import { ApprovalsPage } from "@/features/admin-approvals/components/approvals-page";
import type { RegistrationTab } from "@/features/admin-staff-registrations/api";
import { staffOptionsQuery } from "@/features/auth/staff-api";

interface ApprovalsSearch {
  tab?: Exclude<SignupTab, "student">;
  cohort?: string;
  status?: Exclude<RegistrationTab, "pending">;
}

/**
 * 가입 승인 (F60·F66). 탭 `tab`(기본 수강생, mentor·staff), 기수 `cohort`(수강생 탭),
 * 처리 상태 `status`(운영진 탭, 기본 대기)
 */
export const Route = createFileRoute("/_staff/admin/members/approvals")({
  validateSearch: (search: Record<string, unknown>): ApprovalsSearch => {
    const tab = search.tab === "mentor" || search.tab === "staff" ? search.tab : undefined;
    return {
      ...(tab ? { tab } : {}),
      ...(typeof search.cohort === "string" && search.cohort && !tab ? { cohort: search.cohort } : {}),
      ...(tab === "staff" && (search.status === "approved" || search.status === "rejected")
        ? { status: search.status }
        : {}),
    };
  },
  loader: ({ context }) => context.queryClient.prefetchQuery(staffOptionsQuery),
  component: function Approvals() {
    const { tab, cohort, status } = Route.useSearch();
    return <ApprovalsPage tab={tab} cohortId={cohort} status={status ?? "pending"} />;
  },
});
