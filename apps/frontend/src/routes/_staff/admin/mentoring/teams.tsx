import { createFileRoute, redirect } from "@tanstack/react-router";

import { NoCohort } from "@/features/admin-mentoring/components/no-cohort";
import { staffAccessQuery } from "@/features/staff/api";
import { defaultCohort } from "@/features/staff/current-cohort";

/** 멘토링 > 팀 관리 메뉴: 현재 기수 화면으로 보낸다 (F90·F93) */
export const Route = createFileRoute("/_staff/admin/mentoring/teams")({
  beforeLoad: async ({ context }) => {
    const access = await context.queryClient.ensureQueryData(staffAccessQuery);
    const cohort = defaultCohort(access.cohorts);
    if (cohort)
      throw redirect({
        to: "/admin/cohorts/$cohortId/mentoring/teams",
        params: { cohortId: cohort.id },
        replace: true,
      });
  },
  component: NoCohort,
});
