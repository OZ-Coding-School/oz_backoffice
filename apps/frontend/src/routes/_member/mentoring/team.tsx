import { createFileRoute } from "@tanstack/react-router";

import { myTeamsQuery } from "@/features/apply/api";
import { requireAccount } from "@/features/auth/guards";
import { enrollmentsQuery } from "@/features/member/api";
import { balancesQuery } from "@/features/requests/api";
import { TeamPage } from "@/features/team/components/team-page";

/** 수강생 내 팀 (F39·A73) */
export const Route = createFileRoute("/_member/mentoring/team")({
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["STUDENT"], location);
  },
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.prefetchQuery(myTeamsQuery),
      context.queryClient.prefetchQuery(enrollmentsQuery),
      context.queryClient.prefetchQuery(balancesQuery),
    ]),
  component: TeamPage,
});
