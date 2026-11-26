import { z } from "zod";

import { kstDateKey } from "@/features/apply/slots";
import { formatKst, formatKstDay } from "@/lib/datetime";

import type { UnavailableInput } from "./api";
import { addDays, dayStartMs, type UnavailablePeriod } from "./schedule";

export const CATEGORY_MAX_LENGTH = 30;
export const REASON_MAX_LENGTH = 200;
export const CATEGORY_SUGGESTIONS = ["본업", "강의", "휴가", "개인 일정"] as const;
const WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"];

/** 30분 단위 시각 "00:00" ~ "23:30" */
export const TIME_OPTIONS = Array.from({ length: 48 }, (_, i) => {
  const h = String(Math.floor(i / 2)).padStart(2, "0");
  return `${h}:${i % 2 ? "30" : "00"}`;
});

const DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * 불가 시간 입력 (F53·F88): 시간은 시작·종료 시각만 고르고, 종료가 시작보다 이르면 다음 날로 넘어간다
 * (한 번에 24시간 미만). 날짜는 '적용 기간'으로 따로 받고, 마지막 날은 하루 종일 한 번에서만 쓴다.
 */
export const unavailableSchema = z
  .object({
    repeat: z.enum(["ONCE", "DAILY", "WEEKLY"]),
    allDay: z.boolean(),
    weekdays: z.array(z.number().int().min(1).max(7)),
    startDate: z.string().regex(DATE, "날짜를 골라 주세요."),
    startTime: z.string(),
    endDate: z.string(),
    endTime: z.string(),
    repeatUntil: z.string(),
    category: z.string().trim().max(CATEGORY_MAX_LENGTH, `분류는 ${CATEGORY_MAX_LENGTH}자까지 적을 수 있어요.`),
    reason: z.string().trim().max(REASON_MAX_LENGTH, `메모는 ${REASON_MAX_LENGTH}자까지 적을 수 있어요.`),
  })
  .superRefine((v, ctx) => {
    if (v.repeat === "WEEKLY" && v.weekdays.length === 0)
      ctx.addIssue({ code: "custom", path: ["weekdays"], message: "요일을 하나 이상 골라 주세요." });
    if (isAllDay(v)) {
      if (v.endDate && v.endDate < v.startDate)
        ctx.addIssue({ code: "custom", path: ["endDate"], message: "마지막 날은 첫 날과 같거나 뒤여야 해요." });
    } else if (v.endTime === v.startTime)
      ctx.addIssue({ code: "custom", path: ["endTime"], message: "종료 시각을 시작과 다르게 골라 주세요." });
    if (v.repeat !== "ONCE" && v.repeatUntil && v.repeatUntil < v.startDate)
      ctx.addIssue({ code: "custom", path: ["repeatUntil"], message: "반복 종료는 시작 날짜와 같거나 뒤여야 해요." });
  });

export type UnavailableForm = z.infer<typeof unavailableSchema>;

function kstIso(date: string, time: string): string {
  return new Date(`${date}T${time}:00+09:00`).toISOString();
}

function isAllDay(v: Pick<UnavailableForm, "repeat" | "allDay">): boolean {
  return v.repeat === "ONCE" && v.allDay;
}

/** 종료가 시작보다 같거나 이르면 다음 날 (F88) */
export function crossesMidnight(v: Pick<UnavailableForm, "startTime" | "endTime">): boolean {
  return v.endTime <= v.startTime;
}

/** "HH:mm" + 분 → "HH:mm" (하루를 넘으면 돌아간다) */
function plusMinutes(time: string, minutes: number): string {
  const [h = 0, m = 0] = time.split(":").map(Number);
  const total = (h * 60 + m + minutes) % (24 * 60);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

/** 새로 추가할 때 기본값: 그날 그 시각(기본 09:00)부터 1시간 한 번. 시간표 빈 칸을 누르면 그 날짜·시각 (F88) */
export function emptyForm(day: string, time = "09:00"): UnavailableForm {
  return {
    repeat: "ONCE",
    allDay: false,
    weekdays: [],
    startDate: day,
    startTime: time,
    endDate: "",
    endTime: plusMinutes(time, 60),
    repeatUntil: "",
    category: "",
    reason: "",
  };
}

/** 등록한 불가 시간 → 입력값 (하루 종일은 마지막 날 = 끝 직전 날) */
export function formOf(period: UnavailablePeriod): UnavailableForm {
  const end = Date.parse(period.ends_at);
  return {
    repeat: period.repeat,
    allDay: period.all_day,
    weekdays: [...period.weekdays],
    startDate: kstDateKey(period.starts_at),
    startTime: formatKst(period.starts_at, "HH:mm"),
    endDate: period.all_day ? kstDateKey(new Date(end - 1)) : "",
    endTime: formatKst(end, "HH:mm"),
    repeatUntil: period.repeat_until ?? "",
    category: period.category ?? "",
    reason: period.reason ?? "",
  };
}

/** 입력값 → API 본문 (A37). 시각은 KST로 보낸다 */
export function bodyOf(v: UnavailableForm): UnavailableInput {
  const meta = { category: v.category.trim() || null, reason: v.reason.trim() || null };
  if (isAllDay(v))
    return {
      repeat: "ONCE",
      all_day: true,
      start_date: v.startDate,
      end_date: v.endDate || v.startDate,
      weekdays: [],
      ...meta,
    };
  const endDate = crossesMidnight(v) ? addDays(v.startDate, 1) : v.startDate;
  return {
    repeat: v.repeat,
    all_day: false,
    starts_at: kstIso(v.startDate, v.startTime),
    ends_at: kstIso(endDate, v.endTime),
    weekdays: v.repeat === "WEEKLY" ? [...v.weekdays].sort() : [],
    repeat_until: v.repeat !== "ONCE" && v.repeatUntil ? v.repeatUntil : null,
    ...meta,
  };
}

/** 이미 시작한 한 번 불가 시간은 바꿀 수 없다 (A37) */
export function isLocked(period: UnavailablePeriod, now: number): boolean {
  return period.repeat === "ONCE" && Date.parse(period.starts_at) <= now;
}

function shortDate(key: string): string {
  return formatKst(dayStartMs(key), "M/d");
}

/** 창 아래 요약 한 줄 (F88): "매주 화·수 09:00–12:00 · 11/3부터 12/31까지" */
export function summaryOf(v: UnavailableForm): string {
  if (isAllDay(v)) {
    const last = v.endDate && v.endDate > v.startDate ? v.endDate : null;
    const first = formatKstDay(dayStartMs(v.startDate));
    return last ? `${first} ~ ${formatKstDay(dayStartMs(last))} 하루 종일` : `${first} 하루 종일`;
  }
  const end = crossesMidnight(v) ? (v.endTime === "00:00" ? "24:00" : `다음 날 ${v.endTime}`) : v.endTime;
  const time = `${v.startTime}–${end}`;
  if (v.repeat === "ONCE") return `${formatKstDay(dayStartMs(v.startDate))} ${time}`;
  const range = `${shortDate(v.startDate)}부터 ${v.repeatUntil ? `${shortDate(v.repeatUntil)}까지` : "계속"}`;
  if (v.repeat === "DAILY") return `매일 ${time} · ${range}`;
  const days = [...v.weekdays]
    .sort()
    .map((d) => WEEKDAY_LABELS[d - 1])
    .join("·");
  return `매주 ${days || "(요일을 골라 주세요)"} ${time} · ${range}`;
}
