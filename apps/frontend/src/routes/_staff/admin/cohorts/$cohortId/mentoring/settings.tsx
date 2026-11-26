import { createFileRoute } from "@tanstack/react-router";

import { cohortSettingsQuery } from "@/features/admin-academy/api";
import { blockTimesQuery } from "@/features/admin-mentoring/api";
import { SettingsPage } from "@/features/admin-mentoring/components/settings-page";

/** 멘토링 > 멘토링 설정 (F90·A34·A37). 기수는 주소에 */
export const Route = createFileRoute("/_staff/admin/cohorts/$cohortId/mentoring/settings")({
  loader: ({ context, params }) =>
    Promise.all([
      context.queryClient.prefetchQuery(cohortSettingsQuery(params.cohortId)),
      context.queryClient.prefetchQuery(blockTimesQuery(params.cohortId)),
    ]),
  component: function MentoringSettings() {
    const { cohortId } = Route.useParams();
    return <SettingsPage key={cohortId} cohortId={cohortId} />;
  },
});
