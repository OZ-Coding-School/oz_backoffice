import { z } from "zod";

export const TOPIC_MAX_LENGTH = 100;
export const SUMMARY_MAX_LENGTH = 5000;
export const NOTE_MAX_LENGTH = 5000;
export const RECORD_UNIT_MINUTES = 30;
export const RECORD_EDIT_DAYS = 7;
/** 진행 시간 보기: 30분부터 신청 +120분까지 (F48) */
export const EXTRA_MINUTES = 120;

export function durationOptions(planned: number): number[] {
  const options: number[] = [];
  for (let m = RECORD_UNIT_MINUTES; m <= planned + EXTRA_MINUTES; m += RECORD_UNIT_MINUTES) options.push(m);
  return options;
}

const topic = z
  .string()
  .trim()
  .min(1, "주제를 적어 주세요.")
  .max(TOPIC_MAX_LENGTH, `주제는 ${TOPIC_MAX_LENGTH}자까지 적을 수 있어요.`);
const summary = z
  .string()
  .trim()
  .min(1, "요약을 적어 주세요.")
  .max(SUMMARY_MAX_LENGTH, `요약은 ${SUMMARY_MAX_LENGTH.toLocaleString()}자까지 적을 수 있어요.`);

/** 기록 제출 (A53): 완료는 주제·요약 필수, 노쇼는 사유(선택) */
export const recordSchema = z.discriminatedUnion("status", [
  z.object({ status: z.literal("COMPLETED"), duration: z.number().int().positive(), topic, summary }),
  z.object({
    status: z.literal("NO_SHOW"),
    duration: z.number().optional(),
    topic: z.string().optional(),
    summary: z
      .string()
      .trim()
      .max(SUMMARY_MAX_LENGTH, `사유는 ${SUMMARY_MAX_LENGTH.toLocaleString()}자까지 적을 수 있어요.`),
  }),
]);

export type RecordForm = z.infer<typeof recordSchema>;

/** 기록 수정: 주제·요약만 */
export const editSchema = z.object({ topic, summary });
export type EditForm = z.infer<typeof editSchema>;
