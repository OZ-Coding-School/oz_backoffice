import { createFileRoute } from "@tanstack/react-router";

import { StaffHome } from "@/features/staff/components/staff-home";

/** 운영진 홈 (FE-14a 임시, 요약은 FE-14b) */
export const Route = createFileRoute("/_staff/admin/")({
  component: function AdminHome() {
    const { me } = Route.useRouteContext();
    return <StaffHome me={me} />;
  },
});
