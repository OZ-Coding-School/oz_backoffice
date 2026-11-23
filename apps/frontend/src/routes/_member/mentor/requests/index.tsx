import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import {
  isReceivedTab,
  myAssignmentsQuery,
  receivedRequestsQuery,
  type ReceivedTab,
} from "@/features/mentor-requests/api";
import { ReceivedRequestsPage } from "@/features/mentor-requests/components/received-requests-page";

interface ReceivedSearch {
  tab?: Exclude<ReceivedTab, "pending">;
  cohort?: string;
}

/** 멘토 받은 신청 (F43). 탭 `tab`(기본 대기), 기수 `cohort` */
export const Route = createFileRoute("/_member/mentor/requests/")({
  validateSearch: (search: Record<string, unknown>): ReceivedSearch => ({
    ...(isReceivedTab(search.tab) && search.tab !== "pending" ? { tab: search.tab } : {}),
    ...(typeof search.cohort === "string" && search.cohort ? { cohort: search.cohort } : {}),
  }),
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["MENTOR"], location);
  },
  loaderDeps: ({ search }): { tab: ReceivedTab; cohort?: string } => ({
    tab: search.tab ?? "pending",
    cohort: search.cohort,
  }),
  loader: ({ context, deps }) =>
    Promise.all([
      context.queryClient.prefetchInfiniteQuery(receivedRequestsQuery(deps.tab, deps.cohort)),
      context.queryClient.prefetchQuery(myAssignmentsQuery),
    ]),
  component: function ReceivedRequests() {
    const { tab, cohort } = Route.useSearch();
    return <ReceivedRequestsPage tab={tab ?? "pending"} cohortId={cohort} />;
  },
});
