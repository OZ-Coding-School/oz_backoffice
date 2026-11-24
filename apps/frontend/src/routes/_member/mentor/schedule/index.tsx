import { createFileRoute } from "@tanstack/react-router";

import { kstDateKey } from "@/features/apply/slots";
import { requireAccount } from "@/features/auth/guards";
import { scheduleQuery, weekSessionsQuery } from "@/features/mentor-schedule/api";
import { SchedulePage } from "@/features/mentor-schedule/components/schedule-page";
import { weekStart } from "@/features/mentor-schedule/schedule";

const DATE_KEY = /^\d{4}-\d{2}-\d{2}$/;

/** 멘토 일정 (F51·F52). 주는 검색 파라미터 `week`(그 주의 아무 날, 기본은 이번 주) */
export const Route = createFileRoute("/_member/mentor/schedule/")({
  validateSearch: (search: Record<string, unknown>): { week?: string } =>
    typeof search.week === "string" && DATE_KEY.test(search.week) ? { week: search.week } : {},
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["MENTOR"], location);
  },
  loaderDeps: ({ search }) => ({ monday: weekStart(search.week ?? kstDateKey(new Date())) }),
  loader: ({ context, deps }) =>
    Promise.all([
      context.queryClient.prefetchQuery(scheduleQuery),
      context.queryClient.prefetchQuery(weekSessionsQuery(deps.monday)),
    ]),
  component: function MentorSchedule() {
    const { week } = Route.useSearch();
    return <SchedulePage monday={weekStart(week ?? kstDateKey(new Date()))} />;
  },
});
