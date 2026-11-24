import { createFileRoute } from "@tanstack/react-router";

import { approvalsQuery, type ApprovalTab } from "@/features/admin-approvals/api";
import { ApprovalsPage } from "@/features/admin-approvals/components/approvals-page";

interface ApprovalsSearch {
  type?: "mentor";
  cohort?: string;
}

/** 회원 가입 승인 (F60). 탭 `type`(기본 수강생), 기수 `cohort`(수강생 탭) */
export const Route = createFileRoute("/_staff/admin/members/approvals")({
  validateSearch: (search: Record<string, unknown>): ApprovalsSearch => ({
    ...(search.type === "mentor" ? { type: "mentor" as const } : {}),
    ...(typeof search.cohort === "string" && search.cohort && search.type !== "mentor"
      ? { cohort: search.cohort }
      : {}),
  }),
  loaderDeps: ({ search }): { tab: ApprovalTab; cohort?: string } => ({
    tab: search.type === "mentor" ? "mentor" : "student",
    cohort: search.cohort,
  }),
  loader: ({ context, deps }) => context.queryClient.prefetchInfiniteQuery(approvalsQuery(deps.tab, deps.cohort)),
  component: function Approvals() {
    const { type, cohort } = Route.useSearch();
    return <ApprovalsPage tab={type === "mentor" ? "mentor" : "student"} cohortId={cohort} />;
  },
});
