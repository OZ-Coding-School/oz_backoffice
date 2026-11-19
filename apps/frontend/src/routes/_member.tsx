import { createFileRoute, Outlet } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { MemberShell } from "@/features/member/components/member-shell";

/** 승인된 수강생·멘토만 들어온다 (F20). 수강생·멘토 공통 틀 (F27). */
export const Route = createFileRoute("/_member")({
  beforeLoad: async ({ context, location }) => ({
    me: await requireAccount(context.queryClient, ["STUDENT", "MENTOR"], location),
  }),
  component: function MemberLayout() {
    const { me } = Route.useRouteContext();
    return (
      <MemberShell me={me}>
        <Outlet />
      </MemberShell>
    );
  },
});
