/** 비밀번호 변경 오류 코드 → 문구 (A72) */
export const PASSWORD_CHANGE_ERRORS: Record<string, string> = {
  resend_too_soon: "링크는 1분에 한 번만 보낼 수 있어요. 잠시 후 다시 보내 주세요.",
  rate_limited: "오늘은 더 보낼 수 없어요. 내일 다시 시도해 주세요.",
  password_not_available: "비밀번호로 로그인하는 계정만 바꿀 수 있어요.",
  password_change_not_verified: "인증 시간이 지났어요. 링크를 다시 받아 주세요.",
  invalid_password: "비밀번호 규칙을 모두 지켜 주세요.",
};

export const FALLBACK_ERROR = "잠시 후 다시 시도해 주세요.";
