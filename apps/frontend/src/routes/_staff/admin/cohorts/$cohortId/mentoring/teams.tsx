import { createFileRoute } from "@tanstack/react-router";

import { cohortSettingsQuery } from "@/features/admin-academy/api";
import { TeamsPage } from "@/features/admin-mentoring/components/teams-page";
import { teamsQuery } from "@/features/admin-mentoring/teams-api";

/** 멘토링 > 팀 관리 (F93·A39·A108). 기수는 주소에 */
export const Route = createFileRoute("/_staff/admin/cohorts/$cohortId/mentoring/teams")({
  loader: ({ context, params }) =>
    Promise.all([
      context.queryClient.prefetchQuery(teamsQuery(params.cohortId)),
      context.queryClient.prefetchQuery(cohortSettingsQuery(params.cohortId)),
    ]),
  component: function MentoringTeams() {
    const { cohortId } = Route.useParams();
    return <TeamsPage key={cohortId} cohortId={cohortId} />;
  },
});
