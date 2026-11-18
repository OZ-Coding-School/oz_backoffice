import { createFileRoute, redirect } from "@tanstack/react-router";

import { ensureSession } from "@/features/auth/api";
import { StaffRegistrationPage } from "@/features/auth/components/staff-registration-page";
import { homePath } from "@/features/auth/navigation";

/** 승인 전 운영진만 들어온다 (A11·A61). */
export const Route = createFileRoute("/_staffAuth/staff/registration")({
  beforeLoad: async ({ context }) => {
    const me = await ensureSession(context.queryClient);
    if (!me) throw redirect({ to: "/staff/login" });
    if (me.account_type !== "STAFF" || me.approval_status === "APPROVED") {
      throw redirect({ href: homePath(me), replace: true });
    }
    return { me };
  },
  component: function StaffRegistration() {
    const { me } = Route.useRouteContext();
    return <StaffRegistrationPage me={me} />;
  },
});
