import type { Me } from "./api";

/** 로그인한 사용자의 홈 (F20: 회원 `/`, 운영진 `/admin`). 승인 전 운영진은 정보 입력 화면. */
export function homePath(me: Me): string {
  if (me.account_type === "STAFF") return me.approval_status === "APPROVED" ? "/admin" : "/staff/registration";
  return "/";
}

function isStaffPath(path: string): boolean {
  return path === "/admin" || path.startsWith("/admin/") || path.startsWith("/staff/");
}

/**
 * 로그인 후 갈 곳 (F21): `redirect`가 이 앱 안의 경로이고 그 계정 종류가 들어갈 수 있는 곳이면 그리로, 아니면 홈.
 * 다른 사이트로 보내는 값(`//evil`, `https://…`)은 무시한다.
 */
export function afterLoginPath(me: Me, redirect: string | undefined): string {
  const home = homePath(me);
  if (!redirect || !redirect.startsWith("/") || redirect.startsWith("//") || me.approval_status !== "APPROVED") {
    return home;
  }
  if (redirect.startsWith("/login") || redirect.startsWith("/password-reset")) return home;
  return isStaffPath(redirect) === (me.account_type === "STAFF") ? redirect : home;
}

/** 승인 전 회원은 로그인 화면 위 가입 상태 모달에서 처리한다. */
export function needsSignupStatus(me: Me | null): me is Me {
  return me !== null && me.account_type === "MEMBER" && me.approval_status !== "APPROVED";
}
