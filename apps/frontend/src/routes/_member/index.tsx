import { createFileRoute } from "@tanstack/react-router";

import { MemberHome } from "@/features/member/components/member-home";
import { pendingRequestsQuery, upcomingSessionsQuery } from "@/features/home/api";
import { mentorPendingQuery, mentorUpcomingQuery } from "@/features/home/mentor-api";
import { scheduleQuery } from "@/features/mentor-schedule/api";
import { enrollmentsQuery } from "@/features/member/api";
import { balancesQuery } from "@/features/requests/api";

export const Route = createFileRoute("/_member/")({
  // 홈(수강생 F42, 멘토 F57)에 필요한 조회를 함께 미리 불러온다 (오늘 수·방 목록은 화면과 틀이 부른다)
  loader: ({ context }) =>
    context.me.account_type === "STUDENT"
      ? Promise.all([
          context.queryClient.prefetchQuery(upcomingSessionsQuery),
          context.queryClient.prefetchQuery(pendingRequestsQuery),
          context.queryClient.prefetchQuery(balancesQuery),
          context.queryClient.prefetchQuery(enrollmentsQuery),
        ])
      : context.me.account_type === "MENTOR"
        ? Promise.all([
            context.queryClient.prefetchQuery(mentorUpcomingQuery),
            context.queryClient.prefetchQuery(mentorPendingQuery),
            context.queryClient.prefetchQuery(scheduleQuery),
          ])
        : undefined,
  component: function Home() {
    const { me } = Route.useRouteContext();
    return <MemberHome me={me} />;
  },
});
