import { createContext, useContext } from "react";

/**
 * 일정 화면의 대상 (F85): 기본은 로그인한 멘토 본인(`/me/mentor-schedule`).
 * 운영진 일정 대리(멘토 상세 '일정' 탭)는 `mentorId`를 넣어 운영진 API를 쓰고,
 * 달 이동은 `onMonth`로 그 화면의 주소를 바꾼다 (F89).
 */
export interface ScheduleScope {
  mentorId: string | null;
  onMonth: ((month: string) => void) | null;
  /** 고칠 권한이 없으면 조회만 (패널·목록의 수정·삭제를 숨긴다) */
  readOnly?: boolean;
}

export const ScheduleScopeContext = createContext<ScheduleScope>({ mentorId: null, onMonth: null });

export function useScheduleScope(): ScheduleScope {
  return useContext(ScheduleScopeContext);
}
