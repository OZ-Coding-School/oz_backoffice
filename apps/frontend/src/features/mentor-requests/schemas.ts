import { z } from "zod";

import { REASON_MAX_LENGTH } from "@/features/requests/schemas";

/** 반려 사유: 필수 1~300자 (A42, 시안의 2,000자는 고침 F45) */
export const rejectSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(1, "반려 사유를 적어 주세요.")
    .max(REASON_MAX_LENGTH, `반려 사유는 ${REASON_MAX_LENGTH}자까지 적을 수 있어요.`),
});

export type RejectForm = z.infer<typeof rejectSchema>;
