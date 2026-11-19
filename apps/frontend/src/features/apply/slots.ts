import { addMinutes } from "date-fns";

import { TIME_ZONE, toEpochMs } from "@/lib/datetime";

export interface Interval {
  starts_at: string;
  ends_at: string;
}

const STEP_MINUTES = 30;
/** 신청 가능 시간 조회는 오늘부터 60일, 한 번에 31일까지 (A38) */
export const MAX_DAYS_AHEAD = 60;
export const MAX_RANGE_DAYS = 31;

/** KST 날짜 키 "2026-11-20" */
const KEY_FORMAT = new Intl.DateTimeFormat("en-CA", {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** Intl로 계산해 Date 하위 클래스(TZDate)·브라우저 시간대와 무관하다 */
export function kstDateKey(date: Date | string): string {
  return KEY_FORMAT.format(toEpochMs(date));
}

/**
 * 연속 가능 구간에서 진행 시간(분)으로 시작할 수 있는 30분 경계 시각 (F30: 가능한 시각만).
 * 결과는 KST 날짜별로 묶고 시각순이다.
 */
export function startTimes(intervals: readonly Interval[], duration: number): Map<string, string[]> {
  const byDay = new Map<string, string[]>();
  for (const interval of intervals) {
    const end = new Date(interval.ends_at).getTime();
    let t = ceilToStep(new Date(interval.starts_at));
    while (addMinutes(t, duration).getTime() <= end) {
      const key = kstDateKey(t);
      const list = byDay.get(key) ?? [];
      list.push(t.toISOString());
      byDay.set(key, list);
      t = addMinutes(t, STEP_MINUTES);
    }
  }
  for (const list of byDay.values()) list.sort();
  return byDay;
}

function ceilToStep(date: Date): Date {
  const ms = STEP_MINUTES * 60_000;
  return new Date(Math.ceil(date.getTime() / ms) * ms);
}

/** 진행 시간 선택지: 진행 단위의 배수, 120분까지, 남은 시간 이하 (F30) */
export function durationOptions(unit: number, remaining: number): number[] {
  const options: number[] = [];
  for (let d = unit; d <= 120; d += unit) if (d <= remaining) options.push(d);
  return options;
}

/**
 * 달력에 보이는 달의 조회 범위(KST 날짜): 오늘~오늘+60일과 겹치는 부분, 31일을 넘으면 나눈다.
 * 반환은 [from, to] 쌍 목록 (포함). 브라우저 시간대와 무관하게 KST 날짜 문자열로 계산한다.
 */
export function monthRanges(month: Date, today: Date): [string, string][] {
  const [y, m] = kstDateKey(month).split("-").map(Number) as [number, number];
  const first = Date.UTC(y, m - 1, 1);
  const last = Date.UTC(y, m, 0);
  const todayKey = dayNumber(kstDateKey(today));
  const start = Math.max(first / DAY_MS, todayKey);
  const end = Math.min(last / DAY_MS, todayKey + MAX_DAYS_AHEAD);
  const ranges: [string, string][] = [];
  for (let from = start; from <= end; from += MAX_RANGE_DAYS) {
    ranges.push([dayKey(from), dayKey(Math.min(from + MAX_RANGE_DAYS - 1, end))]);
  }
  return ranges;
}

const DAY_MS = 86_400_000;

/** "2026-11-20" → 1970-01-01부터의 일수 */
function dayNumber(key: string): number {
  const [y, m, d] = key.split("-").map(Number) as [number, number, number];
  return Date.UTC(y, m - 1, d) / DAY_MS;
}

function dayKey(day: number): string {
  return new Date(day * DAY_MS).toISOString().slice(0, 10);
}
