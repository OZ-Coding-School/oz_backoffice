/** 신청 취소 오류 코드 → 문구 */
export const CANCEL_ERROR_MESSAGES: Record<string, string> = {
  cancel_deadline_passed: "취소 마감이 지났어요. 운영진에게 문의해 주세요.",
  request_not_cancelable: "이미 처리된 신청이라 취소할 수 없어요. 화면을 새로 불러왔어요.",
  not_requester: "신청한 사람만 취소할 수 있어요.",
  not_request_party: "신청한 사람만 취소할 수 있어요.",
  invalid_reason: "취소 사유를 1~300자로 적어 주세요.",
};

export const CANCEL_FALLBACK_MESSAGE = "취소하지 못했어요. 잠시 후 다시 시도해 주세요.";

/** 신청 변경 오류: 신청 오류 문구에 취소 조건 오류를 더한다 (F32) */
export const CHANGE_EXTRA_MESSAGES: Record<string, string> = {
  cancel_deadline_passed: "변경 마감이 지났어요. 운영진에게 문의해 주세요.",
  request_not_cancelable: "이미 처리된 신청이라 바꿀 수 없어요.",
  not_requester: "신청한 사람만 바꿀 수 있어요.",
};
