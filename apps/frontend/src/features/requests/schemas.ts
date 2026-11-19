import { z } from "zod";

/** 취소 사유: 필수 1~300자 (A42) */
export const REASON_MAX_LENGTH = 300;

export const cancelSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(1, "취소 사유를 적어 주세요.")
    .max(REASON_MAX_LENGTH, `취소 사유는 ${REASON_MAX_LENGTH}자까지 적을 수 있어요.`),
});

export type CancelForm = z.infer<typeof cancelSchema>;
