import { createFileRoute, Outlet } from "@tanstack/react-router";

import { AuthLayout } from "@/features/auth/components/auth-layout";

/** 수강생·멘토 로그인·재설정 화면 틀 (소개 영역 + 폼). */
export const Route = createFileRoute("/_auth")({
  component: () => (
    <AuthLayout>
      <Outlet />
    </AuthLayout>
  ),
});
