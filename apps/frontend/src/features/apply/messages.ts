/** 신청 오류 코드 → 문구 (POST /mentoring/requests) */
export const CREATE_ERROR_MESSAGES: Record<string, string> = {
  too_many_pending_requests: "승인 대기 중인 신청이 최대 건수예요. 기존 신청이 처리되거나 취소한 뒤 신청해 주세요.",
  insufficient_balance: "남은 1:1 시간이 부족해요. 진행 시간을 줄여 주세요.",
  balance_account_missing: "1:1 시간이 아직 지급되지 않았어요. 운영진에게 문의해 주세요.",
  balance_account_expired: "1:1 시간의 사용 기간이 끝났어요. 운영진에게 문의해 주세요.",
  desired_time_unavailable: "고른 희망 일시 중 이제 신청할 수 없는 시간이 있어요. 일정을 다시 골라 주세요.",
  desired_time_outside_validity: "희망 일시가 1:1 시간의 사용 기간을 벗어났어요. 일정을 다시 골라 주세요.",
  desired_times_overlap: "희망 일시끼리 겹치면 안 돼요. 일정을 다시 골라 주세요.",
  invalid_desired_times: "희망 일시를 다시 골라 주세요.",
  invalid_request_duration: "진행 시간을 다시 골라 주세요.",
  mentor_not_accepting: "멘토가 지금은 신청을 받지 않아요. 다른 멘토를 골라 주세요.",
  mentoring_mode_not_allowed: "이 기수는 1:1 멘토링을 받지 않아요.",
  student_not_enrolled: "수강 중인 수강생만 신청할 수 있어요.",
  not_cohort_student: "수강 중인 수강생만 신청할 수 있어요.",
};

export const CREATE_FALLBACK_MESSAGE = "신청하지 못했어요. 잠시 후 다시 시도해 주세요.";

/** 다시 고르도록 돌려보낼 단계 */
export const CREATE_ERROR_STEP: Record<string, "mentor" | "schedule"> = {
  desired_time_unavailable: "schedule",
  desired_time_outside_validity: "schedule",
  desired_times_overlap: "schedule",
  invalid_desired_times: "schedule",
  invalid_request_duration: "schedule",
  insufficient_balance: "schedule",
  mentor_not_accepting: "mentor",
};
