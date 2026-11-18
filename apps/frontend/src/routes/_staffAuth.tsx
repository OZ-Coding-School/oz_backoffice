import { createFileRoute, Outlet, useLocation } from "@tanstack/react-router";

import { STAFF_BRAND } from "@/features/auth/brand";
import { AuthLayout } from "@/features/auth/components/auth-layout";

/** 운영진 로그인·최초 정보 입력 화면 틀 (소개 영역에 운영진 문구·기능 목록). */
export const Route = createFileRoute("/_staffAuth")({
  component: function StaffAuthLayout() {
    // 정보 입력 폼은 두 칸 배치가 있어 데스크톱에서 넓게(520) 쓴다 (Figma `정보 입력`)
    const wide = useLocation({ select: (l) => l.pathname.startsWith("/staff/registration") });
    return (
      <AuthLayout brand={STAFF_BRAND} wide={wide}>
        <Outlet />
      </AuthLayout>
    );
  },
});
