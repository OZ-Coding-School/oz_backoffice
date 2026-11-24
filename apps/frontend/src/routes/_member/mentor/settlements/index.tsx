import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { myAssignmentsQuery } from "@/features/mentor-requests/api";
import { mySettlementsQuery } from "@/features/mentor-settlements/api";
import { SettlementsPage } from "@/features/mentor-settlements/components/settlements-page";

interface SettlementsSearch {
  cohort?: string;
}

/** 멘토 정산 (F54). 기수 `cohort` */
export const Route = createFileRoute("/_member/mentor/settlements/")({
  validateSearch: (search: Record<string, unknown>): SettlementsSearch =>
    typeof search.cohort === "string" && search.cohort ? { cohort: search.cohort } : {},
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["MENTOR"], location);
  },
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.prefetchQuery(mySettlementsQuery),
      context.queryClient.prefetchQuery(myAssignmentsQuery),
    ]),
  component: function MentorSettlements() {
    const { cohort } = Route.useSearch();
    return <SettlementsPage cohortId={cohort} />;
  },
});
