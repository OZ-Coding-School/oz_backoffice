import { api, unwrap } from "@/api/client";
import { ApiError } from "@/api/errors";

/** 가입 토큰이 없거나 만료돼 처음부터 다시 해야 하는 오류 */
export function isSessionExpired(error: unknown): boolean {
  return error instanceof ApiError && ["signup_session_expired", "token_invalid", "token_expired"].includes(error.code);
}

export const signupApi = {
  sendEmailCode: (email: string) => unwrap(api.POST("/api/v1/auth/signup/email-code", { body: { email } })),
  verifyEmailCode: (email: string, code: string) =>
    unwrap(api.POST("/api/v1/auth/signup/email-code/verify", { body: { email, code } })),
  sendPhoneCode: (signupToken: string, phoneNumber: string) =>
    unwrap(
      api.POST("/api/v1/auth/signup/phone-code", { body: { signup_token: signupToken, phone_number: phoneNumber } }),
    ),
  verifyPhoneCode: (signupToken: string, code: string) =>
    unwrap(api.POST("/api/v1/auth/signup/phone-code/verify", { body: { signup_token: signupToken, code } })),
};
