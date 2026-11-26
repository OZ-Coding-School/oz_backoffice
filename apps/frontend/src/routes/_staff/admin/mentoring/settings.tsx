import { createFileRoute, redirect } from "@tanstack/react-router";

import { NoCohort } from "@/features/admin-mentoring/components/no-cohort";
import { staffAccessQuery } from "@/features/staff/api";
import { defaultCohort } from "@/features/staff/current-cohort";

/** 멘토링 > 멘토링 설정 메뉴: 현재 기수 화면으로 보낸다 (F90) */
export const Route = createFileRoute("/_staff/admin/mentoring/settings")({
  beforeLoad: async ({ context }) => {
    const access = await context.queryClient.ensureQueryData(staffAccessQuery);
    const cohort = defaultCohort(access.cohorts);
    if (cohort)
      throw redirect({
        to: "/admin/cohorts/$cohortId/mentoring/settings",
        params: { cohortId: cohort.id },
        replace: true,
      });
  },
  component: NoCohort,
});
