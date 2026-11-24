import { z } from "zod";

import { kstDateKey } from "@/features/apply/slots";
import { formatKst } from "@/lib/datetime";

import type { UnavailableInput } from "./api";
import type { UnavailablePeriod } from "./schedule";

export const CATEGORY_MAX_LENGTH = 30;
export const REASON_MAX_LENGTH = 200;
export const CATEGORY_SUGGESTIONS = ["본업", "강의", "휴가", "개인 일정"] as const;
const DAY_MINUTES = 24 * 60;

/** 30분 단위 시각 "00:00" ~ "23:30" */
export const TIME_OPTIONS = Array.from({ length: 48 }, (_, i) => {
  const h = String(Math.floor(i / 2)).padStart(2, "0");
  return `${h}:${i % 2 ? "30" : "00"}`;
});

const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** 불가 시간 입력 (F53): 시작·종료 날짜·시각을 따로, 하루 종일은 한 번에서만 */
export const unavailableSchema = z
  .object({
    repeat: z.enum(["ONCE", "DAILY", "WEEKLY"]),
    allDay: z.boolean(),
    weekdays: z.array(z.number().int().min(1).max(7)),
    startDate: z.string().regex(DATE, "날짜를 골라 주세요."),
    startTime: z.string(),
    endDate: z.string().regex(DATE, "날짜를 골라 주세요."),
    endTime: z.string(),
    repeatUntil: z.string(),
    category: z.string().trim().max(CATEGORY_MAX_LENGTH, `분류는 ${CATEGORY_MAX_LENGTH}자까지 적을 수 있어요.`),
    reason: z.string().trim().max(REASON_MAX_LENGTH, `메모는 ${REASON_MAX_LENGTH}자까지 적을 수 있어요.`),
  })
  .superRefine((v, ctx) => {
    if (v.repeat === "WEEKLY" && v.weekdays.length === 0)
      ctx.addIssue({ code: "custom", path: ["weekdays"], message: "요일을 하나 이상 골라 주세요." });
    if (v.allDay && v.repeat === "ONCE") {
      if (v.endDate < v.startDate)
        ctx.addIssue({ code: "custom", path: ["endDate"], message: "마지막 날은 첫 날과 같거나 뒤여야 해요." });
    } else {
      const minutes = spanMinutes(v);
      if (minutes <= 0) ctx.addIssue({ code: "custom", path: ["endTime"], message: "종료는 시작보다 뒤여야 해요." });
      else if (minutes > DAY_MINUTES)
        ctx.addIssue({ code: "custom", path: ["endTime"], message: "한 번에 24시간까지 등록할 수 있어요." });
    }
    if (v.repeat !== "ONCE" && v.repeatUntil && v.repeatUntil < v.startDate)
      ctx.addIssue({ code: "custom", path: ["repeatUntil"], message: "반복 종료는 시작 날짜와 같거나 뒤여야 해요." });
  });

export type UnavailableForm = z.infer<typeof unavailableSchema>;

function kstIso(date: string, time: string): string {
  return new Date(`${date}T${time}:00+09:00`).toISOString();
}

function spanMinutes(v: Pick<UnavailableForm, "startDate" | "startTime" | "endDate" | "endTime">): number {
  return (Date.parse(kstIso(v.endDate, v.endTime)) - Date.parse(kstIso(v.startDate, v.startTime))) / 60_000;
}

/** 새로 추가할 때 기본값: 그날 09:00~10:00 한 번 */
export function emptyForm(day: string): UnavailableForm {
  return {
    repeat: "ONCE",
    allDay: false,
    weekdays: [],
    startDate: day,
    startTime: "09:00",
    endDate: day,
    endTime: "10:00",
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
    endDate: period.all_day ? kstDateKey(new Date(end - 1)) : kstDateKey(period.ends_at),
    endTime: formatKst(end, "HH:mm"),
    repeatUntil: period.repeat_until ?? "",
    category: period.category ?? "",
    reason: period.reason ?? "",
  };
}

/** 입력값 → API 본문 (A37). 시각은 KST로 보낸다 */
export function bodyOf(v: UnavailableForm): UnavailableInput {
  const meta = { category: v.category.trim() || null, reason: v.reason.trim() || null };
  if (v.repeat === "ONCE" && v.allDay)
    return { repeat: "ONCE", all_day: true, start_date: v.startDate, end_date: v.endDate, weekdays: [], ...meta };
  return {
    repeat: v.repeat,
    all_day: false,
    starts_at: kstIso(v.startDate, v.startTime),
    ends_at: kstIso(v.endDate, v.endTime),
    weekdays: v.repeat === "WEEKLY" ? [...v.weekdays].sort() : [],
    repeat_until: v.repeat !== "ONCE" && v.repeatUntil ? v.repeatUntil : null,
    ...meta,
  };
}

/** 이미 시작한 한 번 불가 시간은 바꿀 수 없다 (A37) */
export function isLocked(period: UnavailablePeriod, now: number): boolean {
  return period.repeat === "ONCE" && Date.parse(period.starts_at) <= now;
}
