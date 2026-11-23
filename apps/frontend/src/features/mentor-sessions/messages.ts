/** 기록 제출·수정 오류 코드 → 문구 */
export const RECORD_ERROR_MESSAGES: Record<string, string> = {
  session_not_started: "세션이 시작된 뒤에 기록할 수 있어요.",
  session_not_recordable: "이미 기록했거나 취소된 세션이에요. 화면을 새로 불러왔어요.",
  invalid_record_duration: "진행 시간은 30분 단위로 골라 주세요.",
  invalid_record_topic: "주제를 1~100자로 적어 주세요.",
  invalid_record_summary: "요약을 1~5,000자로 적어 주세요.",
  record_edit_expired: "수정 기한(제출 후 7일)이 지났어요.",
  record_not_submitted: "아직 제출한 기록이 없어요.",
  not_session_mentor: "담당 멘토만 기록할 수 있어요.",
};

export const RECORD_FALLBACK_MESSAGE = "기록을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.";

export const NOTE_FALLBACK_MESSAGE = "메모를 저장하지 못했어요. 잠시 후 다시 시도해 주세요.";
