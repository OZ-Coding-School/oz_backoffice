import { ApiError } from "@/api/errors";
import { formatKst, secondsFromNow } from "@/lib/datetime";

import type { AlertMessage } from "../messages";

/** 코드 유효 10분, 재발송은 60초 뒤 (A30). */
export const CODE_TTL_SECONDS = 10 * 60;
export const RESEND_SECONDS = 60;

/** 429(발송 제한·재발송 간격)를 "HH:mm 이후에 다시 시도" Alert로 (Figma `오류 · 요청 횟수 초과`). */
export function rateLimitAlert(error: unknown): (AlertMessage & { until: Date }) | null {
  if (!(error instanceof ApiError) || error.status !== 429) return null;
  const until = secondsFromNow(error.retryAfterSeconds ?? 60);
  return {
    variant: "warning",
    title: "인증코드 요청이 너무 많아요",
    description: `${formatKst(until, "HH:mm")} 이후에 다시 시도해 주세요.`,
    until,
  };
}
