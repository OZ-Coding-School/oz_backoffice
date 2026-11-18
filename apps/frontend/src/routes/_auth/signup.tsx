import { createFileRoute, redirect } from "@tanstack/react-router";

import { ensureSession } from "@/features/auth/api";
import { SignupPage } from "@/features/auth/components/signup-page";
import { homePath } from "@/features/auth/navigation";

export const Route = createFileRoute("/_auth/signup")({
  // 이미 로그인했으면 가입 화면 대신 홈으로
  beforeLoad: async ({ context }) => {
    const me = await ensureSession(context.queryClient);
    if (me && me.approval_status === "APPROVED") throw redirect({ href: homePath(me), replace: true });
  },
  component: SignupPage,
});
