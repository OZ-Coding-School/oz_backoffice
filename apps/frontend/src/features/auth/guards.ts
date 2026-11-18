import type { QueryClient } from "@tanstack/react-query";
import { redirect } from "@tanstack/react-router";

import { ensureSession, type Me } from "./api";
import { homePath, isMember } from "./navigation";

/**
 * 라우트 가드: 로그인했고 이 영역에 들어갈 수 있는 계정인지 확인한다.
 * - 로그인 안 함 → `/login?redirect=<지금 경로>`
 * - 승인 전 회원 → `/login`(가입 상태 모달), 승인 전 운영진 → 정보 입력 화면
 * - 다른 계정 종류의 영역 → 그 계정의 홈
 */
export async function requireAccount(
  queryClient: QueryClient,
  accountTypes: readonly Me["account_type"][],
  location: { href: string },
): Promise<Me> {
  const me = await ensureSession(queryClient);
  if (!me) throw redirect({ to: "/login", search: { redirect: location.href } });
  if (me.approval_status !== "APPROVED" && isMember(me)) throw redirect({ to: "/login" });
  if (me.approval_status !== "APPROVED" || !accountTypes.includes(me.account_type)) {
    throw redirect({ href: homePath(me) });
  }
  return me;
}
