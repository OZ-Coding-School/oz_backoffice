import type { components } from "@/api/schema.gen";
import { kstDateKey } from "@/features/apply/slots";
import { formatKst, formatKstDay } from "@/lib/datetime";

export type UnavailablePeriod = components["schemas"]["UnavailableResponse"];

const DAY_MS = 24 * 60 * 60_000;
const WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"];

/** KST 날짜 키("2026-11-24")의 그날 00:00 (ms). 한국은 일광 절약 시간이 없다 */
export function dayStartMs(key: string): number {
  return Date.parse(`${key}T00:00:00+09:00`);
}

export function addDays(key: string, days: number): string {
  return kstDateKey(new Date(dayStartMs(key) + days * DAY_MS));
}

/** ISO 요일 (1=월 … 7=일) */
export function isoWeekday(key: string): number {
  const d = new Date(dayStartMs(key) + 12 * 60 * 60_000).getUTCDay(); // 정오(UTC 03시)로 날짜가 바뀌지 않게
  return d === 0 ? 7 : d;
}

/** 그 날짜가 속한 주의 월요일 */
export function weekStart(key: string): string {
  return addDays(key, 1 - isoWeekday(key));
}

export function weekDays(monday: string): string[] {
  return Array.from({ length: 7 }, (_, i) => addDays(monday, i));
}

export function weekdayLabel(key: string): string {
  return WEEKDAY_LABELS[isoWeekday(key) - 1] ?? "";
}

/** "11월 23일 ~ 29일" / 달이 바뀌면 "11월 30일 ~ 12월 6일" */
export function weekTitle(monday: string): string {
  const sunday = addDays(monday, 6);
  const a = formatKst(dayStartMs(monday), "M월 d일");
  const sameMonth = monday.slice(0, 7) === sunday.slice(0, 7);
  return `${a} ~ ${formatKst(dayStartMs(sunday), sameMonth ? "d일" : "M월 d일")}`;
}

/**
 * [from, to)와 겹치는 회차의 (시작, 끝) ms. 백엔드 `MentorUnavailablePeriod.occurrences`와 같은 규칙:
 * 반복은 기준 회차의 한국 시각·길이로 매일 또는 그 요일에, 반복 종료일까지(그날 시작 회차 포함).
 */
export function occurrences(period: UnavailablePeriod, from: number, to: number): [number, number][] {
  const start = Date.parse(period.starts_at);
  const end = Date.parse(period.ends_at);
  if (period.repeat === "ONCE") return start < to && from < end ? [[start, end]] : [];
  const length = end - start;
  const firstKey = kstDateKey(period.starts_at);
  const offset = start - dayStartMs(firstKey); // 기준 회차의 하루 안 시각
  // 자정을 넘는 회차가 있으므로 하루 앞에서부터 본다
  let key = kstDateKey(new Date(Math.max(dayStartMs(firstKey), from - DAY_MS)));
  if (key < firstKey) key = firstKey;
  let last = kstDateKey(new Date(to));
  if (period.repeat_until && period.repeat_until < last) last = period.repeat_until;
  const result: [number, number][] = [];
  while (key <= last) {
    if (period.repeat === "DAILY" || period.weekdays.includes(isoWeekday(key))) {
      const s = dayStartMs(key) + offset;
      if (s < to && from < s + length) result.push([s, s + length]);
    }
    key = addDays(key, 1);
  }
  return result;
}

/** 하루 칸에 그릴 조각: 그날 00:00 기준 분 [시작, 끝) (자정을 넘으면 나눠 그린다) */
export function daySegment(range: [number, number], key: string): [number, number] | null {
  const dayStart = dayStartMs(key);
  const s = Math.max(range[0], dayStart);
  const e = Math.min(range[1], dayStart + DAY_MS);
  if (s >= e) return null;
  return [(s - dayStart) / 60_000, (e - dayStart) / 60_000];
}

const REPEAT_LABELS = { ONCE: "한 번", DAILY: "매일", WEEKLY: "매주" } as const;

export function repeatLabel(period: Pick<UnavailablePeriod, "repeat">): string {
  return REPEAT_LABELS[period.repeat];
}

function hm(ms: number): string {
  return formatKst(ms, "HH:mm");
}

/**
 * 목록 한 줄 (시안): "매주 화·수·목·금 09:00~12:00 · 12/31까지", "11/23(월) 19:00~21:00",
 * "12/24(목) 하루 종일 ~ 12/26(토)". 자정을 넘으면 끝 시각 앞에 '다음 날'.
 */
export function periodLabel(period: UnavailablePeriod): string {
  const start = Date.parse(period.starts_at);
  const end = Date.parse(period.ends_at);
  // 끝이 그날 안이면 그대로(자정은 24:00), 다음 날로 넘어가면 '다음 날'
  const sameDay = kstDateKey(new Date(end - 1)) === kstDateKey(new Date(start));
  const endText = sameDay ? (hm(end) === "00:00" ? "24:00" : hm(end)) : `다음 날 ${hm(end)}`;
  const range = `${hm(start)}~${endText}`;
  const until = period.repeat_until ? ` · ${formatKst(dayStartMs(period.repeat_until), "MM/dd")}까지` : "";
  if (period.repeat === "DAILY") return `매일 ${range}${until}`;
  if (period.repeat === "WEEKLY") {
    const days = [...period.weekdays]
      .sort()
      .map((d) => WEEKDAY_LABELS[d - 1])
      .join("·");
    return `매주 ${days} ${range}${until}`;
  }
  if (period.all_day) {
    const lastDay = new Date(end - 1);
    const oneDay = kstDateKey(lastDay) === kstDateKey(new Date(start));
    return oneDay ? `${formatKstDay(start)} 하루 종일` : `${formatKstDay(start)} 하루 종일 ~ ${formatKstDay(lastDay)}`;
  }
  return `${formatKstDay(start)} ${range}`;
}
