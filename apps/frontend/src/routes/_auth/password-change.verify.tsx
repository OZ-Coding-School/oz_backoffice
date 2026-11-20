import { createFileRoute } from "@tanstack/react-router";

import { PasswordVerifyPage } from "@/features/profile/components/password-verify-page";

/** 비밀번호 변경 메일 링크 (A72). 로그인 없이 연다 */
export const Route = createFileRoute("/_auth/password-change/verify")({
  validateSearch: (search: Record<string, unknown>): { token?: string } =>
    typeof search.token === "string" ? { token: search.token } : {},
  component: function PasswordVerify() {
    const { token } = Route.useSearch();
    return <PasswordVerifyPage token={token ?? ""} />;
  },
});
