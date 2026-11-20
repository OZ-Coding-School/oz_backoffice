import { useNavigate } from "@tanstack/react-router";

import { logout } from "@/features/auth/api";

/** 로그아웃 후 로그인 화면으로 (사이드바 사용자 카드·사용자 메뉴·내 정보가 함께 쓴다) */
export function useLogout() {
  const navigate = useNavigate();
  return async () => {
    await logout();
    await navigate({ to: "/login", replace: true });
  };
}
