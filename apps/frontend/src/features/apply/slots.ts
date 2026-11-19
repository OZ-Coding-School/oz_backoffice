import { addDays, addMinutes, differenceInCalendarDays, format } from "date-fns";
import { TZDate } from "@date-fns/tz";

import { TIME_ZONE } from "@/lib/datetime";

export interface Interval {
  starts_at: string;
  ends_at: string;
}

const STEP_MINUTES = 30;
/** 신청 가능 시간 조회는 오늘부터 60일, 한 번에 31일까지 (A38) */
export const MAX_DAYS_AHEAD = 60;
export const MAX_RANGE_DAYS = 31;

/** KST 날짜 키 "2026-11-20" */
export function kstDateKey(date: Date | string): string {
  return format(new TZDate(new Date(date).getTime(), TIME_ZONE), "yyyy-MM-dd");
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
 * 반환은 [from, to] 쌍 목록 (포함).
 */
export function monthRanges(month: Date, today: Date): [string, string][] {
  const first = new TZDate(month.getFullYear(), month.getMonth(), 1, TIME_ZONE);
  const last = new TZDate(month.getFullYear(), month.getMonth() + 1, 0, TIME_ZONE);
  const start = maxDate(first, startOfKstDay(today));
  const end = minDate(last, addDays(startOfKstDay(today), MAX_DAYS_AHEAD));
  if (differenceInCalendarDays(end, start) < 0) return [];
  const ranges: [string, string][] = [];
  let from: Date = start;
  while (differenceInCalendarDays(end, from) >= 0) {
    const to = minDate(addDays(from, MAX_RANGE_DAYS - 1), end);
    ranges.push([kstDateKey(from), kstDateKey(to)]);
    from = addDays(to, 1);
  }
  return ranges;
}

function startOfKstDay(date: Date): Date {
  const d = new TZDate(date.getTime(), TIME_ZONE);
  return new TZDate(d.getFullYear(), d.getMonth(), d.getDate(), TIME_ZONE);
}

const maxDate = (a: Date, b: Date) => (a.getTime() >= b.getTime() ? a : b);
const minDate = (a: Date, b: Date) => (a.getTime() <= b.getTime() ? a : b);
