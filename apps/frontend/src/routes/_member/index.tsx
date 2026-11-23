import { createFileRoute } from "@tanstack/react-router";

import { MemberHome } from "@/features/member/components/member-home";
import { pendingRequestsQuery, upcomingSessionsQuery } from "@/features/home/api";
import { enrollmentsQuery } from "@/features/member/api";
import { balancesQuery } from "@/features/requests/api";

export const Route = createFileRoute("/_member/")({
  // 수강생 홈(F42)에 필요한 조회를 함께 미리 불러온다 (오늘 수·방 목록은 화면과 틀이 부른다)
  loader: ({ context }) =>
    context.me.account_type === "STUDENT"
      ? Promise.all([
          context.queryClient.prefetchQuery(upcomingSessionsQuery),
          context.queryClient.prefetchQuery(pendingRequestsQuery),
          context.queryClient.prefetchQuery(balancesQuery),
          context.queryClient.prefetchQuery(enrollmentsQuery),
        ])
      : undefined,
  component: function Home() {
    const { me } = Route.useRouteContext();
    return <MemberHome me={me} />;
  },
});
