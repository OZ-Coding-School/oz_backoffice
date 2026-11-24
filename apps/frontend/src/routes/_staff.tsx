import { createFileRoute, Outlet } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { staffAccessQuery } from "@/features/staff/api";
import { StaffShell } from "@/features/staff/components/staff-shell";

/** 승인된 운영진만 들어온다 (F20). 운영진 틀 (F3·F17·F58) */
export const Route = createFileRoute("/_staff")({
  beforeLoad: async ({ context, location }) => ({
    me: await requireAccount(context.queryClient, ["STAFF"], location),
  }),
  // 메뉴를 권한으로 고르므로 틀을 그리기 전에 받아 둔다 (A81)
  loader: ({ context }) => context.queryClient.ensureQueryData(staffAccessQuery),
  component: function StaffLayout() {
    const { me } = Route.useRouteContext();
    return (
      <StaffShell me={me}>
        <Outlet />
      </StaffShell>
    );
  },
});
