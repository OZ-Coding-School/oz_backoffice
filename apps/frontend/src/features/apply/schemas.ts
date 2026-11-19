import { z } from "zod";

export const TOPIC_MAX_LENGTH = 100;
export const DETAIL_MAX_LENGTH = 2000;

/** 신청 내용 (A42): 주제 1~100자, 상세 1~2,000자(마크다운 원문) */
export const contentSchema = z.object({
  topic: z.string().trim().min(1, "주제를 적어 주세요.").max(TOPIC_MAX_LENGTH, `주제는 ${TOPIC_MAX_LENGTH}자까지예요.`),
  detail: z
    .string()
    .trim()
    .min(1, "상세 내용을 적어 주세요.")
    .max(DETAIL_MAX_LENGTH, `상세 내용은 ${DETAIL_MAX_LENGTH.toLocaleString()}자까지예요.`),
});

export type ContentForm = z.infer<typeof contentSchema>;
