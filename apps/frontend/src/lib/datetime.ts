import { TZDate } from "@date-fns/tz";
import { format } from "date-fns";
import { ko } from "date-fns/locale";

/** 화면 표시는 Asia/Seoul로 한다 (plan §2.5). */
export const TIME_ZONE = "Asia/Seoul";

/**
 * 시각(ms). Date(TZDate 포함)는 getTime()으로 읽는다.
 * `new Date(tzDate)`는 문자열을 거쳐 바뀌어 한국 밖 시간대에서 날짜가 어긋난다.
 */
export function toEpochMs(date: Date | string | number): number {
  // instanceof Date는 쓰지 않는다: 가짜 시계(테스트)나 다른 영역의 Date에서 거짓이 된다
  return typeof date === "object" ? date.getTime() : new Date(date).getTime();
}

export function formatKst(date: Date | string | number, pattern: string): string {
  return format(new TZDate(toEpochMs(date), TIME_ZONE), pattern, { locale: ko });
}

/** "11/16(월)" */
export function formatKstDay(date: Date | string | number): string {
  return formatKst(date, "M/d(EEE)");
}

/** "11/16(월) 10:02" */
export function formatKstDayTime(date: Date | string | number): string {
  return formatKst(date, "M/d(EEE) HH:mm");
}

/** 분 → "1시간", "1시간 30분", "30분" */
export function formatMinutes(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest}분`;
  return rest === 0 ? `${hours}시간` : `${hours}시간 ${rest}분`;
}

/** 지금부터 seconds초 뒤의 시각 (Retry-After → "HH:mm부터 다시 시도"). */
export function secondsFromNow(seconds: number, now: number = Date.now()): Date {
  return new Date(now + seconds * 1000);
}
