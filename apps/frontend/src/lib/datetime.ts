import { TZDate } from "@date-fns/tz";
import { format } from "date-fns";
import { ko } from "date-fns/locale";

/** 화면 표시는 Asia/Seoul로 한다 (plan §2.5). */
export const TIME_ZONE = "Asia/Seoul";

export function formatKst(date: Date | string | number, pattern: string): string {
  return format(new TZDate(new Date(date).getTime(), TIME_ZONE), pattern, { locale: ko });
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
