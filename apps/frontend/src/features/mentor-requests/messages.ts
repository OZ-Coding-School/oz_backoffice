/** 승인 실패 중 그 일시에 표시할 것 (F45) */
export const SLOT_CONFLICT_CODES = new Set(["mentor_schedule_conflict", "participant_schedule_conflict"]);
export const SLOT_PASSED_CODE = "desired_time_passed";

/** 승인 오류 코드 → 문구 */
export const APPROVE_ERROR_MESSAGES: Record<string, string> = {
  mentor_schedule_conflict: "다른 세션과 겹쳐 승인하지 못했어요. 다른 일시를 골라 주세요.",
  participant_schedule_conflict: "신청자의 다른 세션과 겹쳐 승인하지 못했어요. 다른 일시를 골라 주세요.",
  desired_time_passed: "이미 시작 시각이 지난 일시예요. 다른 일시를 골라 주세요.",
  request_not_pending: "이미 처리된 신청이에요. 화면을 새로 불러왔어요.",
  not_desired_time: "희망 일시 중에서 골라 주세요.",
};

export const APPROVE_FALLBACK_MESSAGE = "승인하지 못했어요. 잠시 후 다시 시도해 주세요.";

/** 반려 오류 코드 → 문구 */
export const REJECT_ERROR_MESSAGES: Record<string, string> = {
  request_not_pending: "이미 처리된 신청이에요. 화면을 새로 불러왔어요.",
  invalid_reason: "반려 사유를 1~300자로 적어 주세요.",
};

export const REJECT_FALLBACK_MESSAGE = "반려하지 못했어요. 잠시 후 다시 시도해 주세요.";
