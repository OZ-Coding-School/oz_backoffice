import { TZDate } from "@date-fns/tz";
import { format } from "date-fns";

/** 화면 표시는 Asia/Seoul로 한다 (plan §2.5). */
export const TIME_ZONE = "Asia/Seoul";

export function formatKst(date: Date | string | number, pattern: string): string {
  return format(new TZDate(new Date(date).getTime(), TIME_ZONE), pattern);
}

/** 지금부터 seconds초 뒤의 시각 (Retry-After → "HH:mm부터 다시 시도"). */
export function secondsFromNow(seconds: number, now: number = Date.now()): Date {
  return new Date(now + seconds * 1000);
}
