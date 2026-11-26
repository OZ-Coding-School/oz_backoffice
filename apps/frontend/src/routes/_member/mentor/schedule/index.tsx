import { createFileRoute } from "@tanstack/react-router";

import { kstDateKey } from "@/features/apply/slots";
import { requireAccount } from "@/features/auth/guards";
import { monthSessionsQueryOf, scheduleQuery } from "@/features/mentor-schedule/api";
import { SchedulePage } from "@/features/mentor-schedule/components/schedule-page";
import { monthOf } from "@/features/mentor-schedule/schedule";

const MONTH_KEY = /^\d{4}-(0[1-9]|1[0-2])$/;

/** 멘토 일정 (F51·F89). 달은 검색 파라미터 `month`("2026-11", 기본은 이번 달) */
export const Route = createFileRoute("/_member/mentor/schedule/")({
  validateSearch: (search: Record<string, unknown>): { month?: string } =>
    typeof search.month === "string" && MONTH_KEY.test(search.month) ? { month: search.month } : {},
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["MENTOR"], location);
  },
  loaderDeps: ({ search }) => ({ month: search.month ?? monthOf(kstDateKey(new Date())) }),
  loader: ({ context, deps }) =>
    Promise.all([
      context.queryClient.prefetchQuery(scheduleQuery),
      context.queryClient.prefetchQuery(monthSessionsQueryOf(deps.month, null)),
    ]),
  component: function MentorSchedule() {
    const { month } = Route.useSearch();
    return <SchedulePage month={month ?? monthOf(kstDateKey(new Date()))} />;
  },
});
