/**
 * 공휴일 달력의 날짜 계산 (F72). 날짜는 'YYYY-MM-DD' 문자열로만 다루고,
 * 요일·말일은 UTC 기준 Date로 계산해 브라우저 시간대와 무관하게 한다.
 */

import { formatKst } from "@/lib/datetime";

const pad = (n: number) => String(n).padStart(2, "0");

export function dateKey(year: number, month: number, day: number): string {
  return `${year}-${pad(month)}-${pad(day)}`;
}

/** 0=일 … 6=토 */
export function weekday(key: string): number {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(Date.UTC(y ?? 0, (m ?? 1) - 1, d ?? 1)).getUTCDay();
}

export function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/** 한 달 칸: 1일 앞은 빈 칸(null), 이후 날짜 키 */
export function monthCells(year: number, month: number): (string | null)[] {
  const first = weekday(dateKey(year, month, 1));
  const days = Array.from({ length: daysInMonth(year, month) }, (_, i) => dateKey(year, month, i + 1));
  return [...Array.from({ length: first }, () => null), ...days];
}

export function isDateKey(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [y, m, d] = value.split("-").map(Number) as [number, number, number];
  return m >= 1 && m <= 12 && d >= 1 && d <= daysInMonth(y, m);
}

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
export const WEEKDAY_LABELS = WEEKDAYS;

/** '2026년 6월 5일 (금)' */
export function longLabel(key: string): string {
  const [y, m, d] = key.split("-").map(Number);
  return `${y}년 ${m}월 ${d}일 (${WEEKDAYS[weekday(key)]})`;
}

/** '7/1 (수)' */
export function shortLabel(key: string): string {
  const [, m, d] = key.split("-").map(Number);
  return `${m}/${d} (${WEEKDAYS[weekday(key)]})`;
}

/** 올해 (KST) */
export function kstYear(now: number = Date.now()): number {
  return Number(formatKst(now, "yyyy"));
}
