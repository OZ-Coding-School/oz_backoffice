import { createFileRoute, redirect } from "@tanstack/react-router";
import { z } from "zod";

import { ensureSession } from "@/features/auth/api";
import { StaffLoginPage } from "@/features/auth/components/staff-login-page";
import { homePath } from "@/features/auth/navigation";

export const Route = createFileRoute("/_staffAuth/staff/login")({
  /** 백엔드 Google 콜백이 실패하면 `?error=<code>`로 돌려보낸다 (A61). */
  validateSearch: z.object({ error: z.string().optional() }),
  beforeLoad: async ({ context }) => {
    const me = await ensureSession(context.queryClient);
    if (me) throw redirect({ href: homePath(me), replace: true });
  },
  component: function StaffLogin() {
    const { error } = Route.useSearch();
    return <StaffLoginPage error={error} />;
  },
});
