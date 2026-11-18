import type { AlertProps } from "@/components/ui/alert";

/** 로그인 화면 Alert 문구 (Figma Login / 개발 메모, decisions F20). */
export interface AlertMessage {
  variant: NonNullable<AlertProps["variant"]>;
  title: string;
  description?: string;
}

export const LOGIN_ERRORS: Record<string, AlertMessage> = {
  invalid_credentials: { variant: "error", title: "이메일 또는 비밀번호가 올바르지 않아요" },
  account_disabled: { variant: "error", title: "사용할 수 없는 계정이에요", description: "관리자에게 문의해 주세요." },
};

/** 운영진 Google 로그인 실패 (`/staff/login?error=`, Figma Login / 개발 메모, A61). */
export const GOOGLE_LOGIN_ERRORS: Record<string, AlertMessage> = {
  google_domain_not_allowed: {
    variant: "error",
    title: "회사 Google 계정으로만 로그인할 수 있어요",
    description: "@nextrunners.co.kr 계정을 선택해 다시 시도해 주세요.",
  },
  google_login_cancelled: { variant: "info", title: "Google 로그인을 취소했어요" },
  oauth_state_invalid: { variant: "warning", title: "로그인 요청이 만료됐어요", description: "다시 시도해 주세요." },
  google_auth_failed: {
    variant: "error",
    title: "Google 로그인에 실패했어요",
    description: "잠시 후 다시 시도해 주세요.",
  },
  account_disabled: { variant: "error", title: "사용할 수 없는 계정이에요", description: "관리자에게 문의해 주세요." },
};

export const STAFF_ROLE_LABELS = { MANAGER: "운영 매니저", ASSISTANT: "조교" } as const;

export const EMPLOYMENT_TYPE_LABELS: Record<string, string> = {
  REGULAR: "정규직",
  CONTRACT: "계약직",
  INTERN: "인턴",
  PART_TIME_JOB: "아르바이트",
  FREELANCER: "프리랜서",
  DAILY: "일용직",
};

/** 세션이 끝나 로그인 화면으로 돌아왔을 때. 처음 방문(쿠키 없음)·로그아웃은 안내하지 않는다. */
export function sessionEndedMessage(reason: string | null): AlertMessage | null {
  if (!reason) return null;
  if (reason === "refresh_token_reused") {
    return {
      variant: "warning",
      title: "보안을 위해 로그아웃됐어요",
      description: "다른 곳에서 같은 로그인 정보가 다시 쓰여 모든 기기에서 로그아웃했어요. 다시 로그인해 주세요.",
    };
  }
  if (reason === "account_disabled") return LOGIN_ERRORS.account_disabled ?? null;
  if (["refresh_token_revoked", "token_expired", "token_invalid"].includes(reason)) {
    return { variant: "info", title: "로그인이 만료됐어요", description: "다시 로그인해 주세요." };
  }
  return null;
}

export const VERIFICATION_ERRORS: Record<string, string> = {
  invalid_verification_code: "인증코드가 맞지 않아요.",
  verification_code_expired: "인증코드가 만료됐어요. 코드를 다시 받아 주세요.",
  verification_attempts_exceeded: "5번 틀려 이 코드는 더 쓸 수 없어요. 코드를 다시 받아 주세요.",
};

export const ROLE_LABELS: Record<string, string> = {
  SUPER_ADMIN: "최고 관리자",
  TEAM_LEAD: "팀리드",
  COHORT_MANAGER: "운영 매니저",
  COHORT_ASSISTANT: "조교",
  MENTOR: "멘토",
  STUDENT: "수강생",
};
