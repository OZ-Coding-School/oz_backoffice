import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { myAssignmentsQuery } from "@/features/mentor-requests/api";
import { isMentorSessionTab, mentorSessionsQuery, type MentorSessionTab } from "@/features/mentor-sessions/api";
import { MentorSessionsPage } from "@/features/mentor-sessions/components/mentor-sessions-page";

interface MentorSessionsSearch {
  tab?: Exclude<MentorSessionTab, "upcoming">;
  cohort?: string;
}

/** 멘토 세션 (F46). 탭 `tab`(기본 다가오는), 기수 `cohort` */
export const Route = createFileRoute("/_member/mentor/sessions/")({
  validateSearch: (search: Record<string, unknown>): MentorSessionsSearch => ({
    ...(isMentorSessionTab(search.tab) && search.tab !== "upcoming" ? { tab: search.tab } : {}),
    ...(typeof search.cohort === "string" && search.cohort ? { cohort: search.cohort } : {}),
  }),
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["MENTOR"], location);
  },
  loaderDeps: ({ search }): { tab: MentorSessionTab; cohort?: string } => ({
    tab: search.tab ?? "upcoming",
    cohort: search.cohort,
  }),
  loader: ({ context, deps }) =>
    Promise.all([
      context.queryClient.prefetchInfiniteQuery(mentorSessionsQuery(deps.tab, deps.cohort)),
      context.queryClient.prefetchQuery(myAssignmentsQuery),
    ]),
  component: function MentorSessions() {
    const { tab, cohort } = Route.useSearch();
    return <MentorSessionsPage tab={tab ?? "upcoming"} cohortId={cohort} />;
  },
});
