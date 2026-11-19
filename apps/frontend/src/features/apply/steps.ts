/** 1:1 신청 단계 (F30) */
export const STEPS = [
  { value: "mentor", label: "멘토 선택" },
  { value: "schedule", label: "일정 선택" },
  { value: "content", label: "신청 내용" },
  { value: "confirm", label: "신청 확인" },
] as const;

export type FormStep = (typeof STEPS)[number]["value"];
