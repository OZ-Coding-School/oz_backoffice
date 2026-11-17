import { createFileRoute } from "@tanstack/react-router";

import { TempHome } from "@/features/auth/components/temp-home";

export const Route = createFileRoute("/_staff/admin")({
  component: function StaffHome() {
    const { me } = Route.useRouteContext();
    return <TempHome me={me} />;
  },
});
