import { createFileRoute, redirect } from "@tanstack/react-router";
import { z } from "zod";

import { ensureSession } from "@/features/auth/api";
import { LoginPage } from "@/features/auth/components/login-page";
import { afterLoginPath, needsSignupStatus } from "@/features/auth/navigation";

const search = z.object({
  /** 로그인 후 돌아갈 경로 (F21) */
  redirect: z.string().optional(),
  /** 비밀번호 재설정 후 채워 둘 이메일 */
  email: z.string().optional(),
});

export const Route = createFileRoute("/_auth/login")({
  validateSearch: search,
  beforeLoad: async ({ context, search: { redirect: target } }) => {
    const me = await ensureSession(context.queryClient);
    // 이미 로그인했으면 들어갈 곳으로. 승인 전 회원은 이 화면에서 가입 상태 모달을 본다
    if (me && !needsSignupStatus(me)) throw redirect({ href: afterLoginPath(me, target), replace: true });
    return { me };
  },
  component: function Login() {
    const { me } = Route.useRouteContext();
    const { redirect: target, email } = Route.useSearch();
    return <LoginPage me={me} redirect={target} email={email} />;
  },
});
