import { z } from "zod";

import type { BlockTime, BlockTimeBody, MentoringSettings, SettingsBody } from "./api";

/** 30분 단위 시각. 운영시간 끝은 24:00까지 (A37) */
const slots = (from: number, to: number) =>
  Array.from({ length: to - from + 1 }, (_, i) => {
    const m = (from + i) * 30;
    return `${String(Math.floor(m / 60)).padStart(2, "0")}:${m % 60 ? "30" : "00"}`;
  });
export const START_TIMES = slots(0, 47); // 00:00 ~ 23:30
export const END_TIMES = slots(1, 48); // 00:30 ~ 24:00
/** 금지 시간대는 하루 안 (시각 타입이라 24:00이 없다) */
export const BLOCK_END_TIMES = slots(1, 47);

export const REASON_MAX_LENGTH = 200;
const MAX_GRANT_HOURS = 999;

const hours = z
  .string()
  .trim()
  .regex(/^\d{1,3}$/, "0 이상의 시간(정수)으로 적어 주세요.");

/** 기수 멘토링 설정 입력 (A34·A37). 지급 시간은 시간 단위로 받아 분으로 보낸다 */
export const settingsSchema = z
  .object({
    allow1on1: z.boolean(),
    allowTeam: z.boolean(),
    duration: z.enum(["30", "60"]),
    grant1on1: hours,
    grantTeam: hours,
    pending: z.enum(["1", "2", "3"]),
    lead: z.enum(["6", "12", "24"]),
    weekdayOn: z.boolean(),
    weekdayStart: z.string(),
    weekdayEnd: z.string(),
    weekendOn: z.boolean(),
    weekendStart: z.string(),
    weekendEnd: z.string(),
  })
  .superRefine((v, ctx) => {
    if (!v.allow1on1 && !v.allowTeam)
      ctx.addIssue({ code: "custom", path: ["allow1on1"], message: "1:1과 팀 멘토링 중 하나 이상을 허용해 주세요." });
    for (const [on, start, end, path] of [
      [v.weekdayOn, v.weekdayStart, v.weekdayEnd, "weekdayEnd"],
      [v.weekendOn, v.weekendStart, v.weekendEnd, "weekendEnd"],
    ] as const)
      if (on && end <= start) ctx.addIssue({ code: "custom", path: [path], message: "끝은 시작보다 뒤여야 해요." });
    for (const path of ["grant1on1", "grantTeam"] as const)
      if (Number(v[path]) > MAX_GRANT_HOURS)
        ctx.addIssue({ code: "custom", path: [path], message: `${MAX_GRANT_HOURS}시간까지 적을 수 있어요.` });
  });

export type SettingsForm = z.infer<typeof settingsSchema>;

/** 저장한 설정 → 입력값. 아직 없으면 백엔드 기본값(1:1만, 평일 10:00~19:00, A34·A37) */
export function settingsForm(s: MentoringSettings | null): SettingsForm {
  return {
    allow1on1: s ? s.allow_1_on_1 : true,
    allowTeam: s?.allow_team_mentoring ?? false,
    duration: String(s?.allowed_duration ?? 30) as SettingsForm["duration"],
    grant1on1: String((s?.default_1on1_minutes ?? 0) / 60),
    grantTeam: String((s?.default_team_minutes ?? 0) / 60),
    pending: String(s?.max_pending_requests ?? 1) as SettingsForm["pending"],
    lead: String(s?.min_lead_hours ?? 24) as SettingsForm["lead"],
    weekdayOn: s ? s.weekday_hours !== null : true,
    weekdayStart: s?.weekday_hours?.start ?? "10:00",
    weekdayEnd: s?.weekday_hours?.end ?? "19:00",
    weekendOn: !!s?.weekend_hours,
    weekendStart: s?.weekend_hours?.start ?? "10:00",
    weekendEnd: s?.weekend_hours?.end ?? "18:00",
  };
}

export function settingsBody(v: SettingsForm): SettingsBody {
  return {
    allow_1_on_1: v.allow1on1,
    allow_team_mentoring: v.allowTeam,
    allowed_duration: Number(v.duration) as SettingsBody["allowed_duration"],
    default_1on1_minutes: Number(v.grant1on1) * 60,
    default_team_minutes: Number(v.grantTeam) * 60,
    max_pending_requests: Number(v.pending),
    min_lead_hours: Number(v.lead) as SettingsBody["min_lead_hours"],
    weekday_hours: v.weekdayOn ? { start: v.weekdayStart, end: v.weekdayEnd } : null,
    weekend_hours: v.weekendOn ? { start: v.weekendStart, end: v.weekendEnd } : null,
  };
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** 금지 시간대 입력 (A34): 기간(시작~끝 날짜)·시각(시작~끝)·사유 */
export const blockSchema = z
  .object({
    periodStart: z.string().regex(DATE, "날짜를 골라 주세요."),
    periodEnd: z.string().regex(DATE, "날짜를 골라 주세요."),
    startTime: z.string(),
    endTime: z.string(),
    reason: z.string().trim().max(REASON_MAX_LENGTH, `사유는 ${REASON_MAX_LENGTH}자까지 적을 수 있어요.`),
  })
  .superRefine((v, ctx) => {
    if (DATE.test(v.periodStart) && DATE.test(v.periodEnd) && v.periodEnd < v.periodStart)
      ctx.addIssue({ code: "custom", path: ["periodEnd"], message: "끝 날짜는 시작 날짜와 같거나 뒤여야 해요." });
    if (v.endTime <= v.startTime)
      ctx.addIssue({ code: "custom", path: ["endTime"], message: "끝 시각은 시작보다 뒤여야 해요." });
  });

export type BlockForm = z.infer<typeof blockSchema>;

export function blockForm(b: BlockTime | null): BlockForm {
  return {
    periodStart: b?.period_start ?? "",
    periodEnd: b?.period_end ?? "",
    startTime: b?.start_time.slice(0, 5) ?? "09:00",
    endTime: b?.end_time.slice(0, 5) ?? "18:00",
    reason: b?.reason ?? "",
  };
}

export function blockBody(v: BlockForm): BlockTimeBody {
  return {
    period_start: v.periodStart,
    period_end: v.periodEnd,
    start_time: v.startTime,
    end_time: v.endTime,
    reason: v.reason.trim() || null,
  };
}

/** "11/01 ~ 12/20 · 09:00 ~ 18:00" */
export function blockLabel(b: Pick<BlockTime, "period_start" | "period_end" | "start_time" | "end_time">): string {
  const md = (k: string) => `${k.slice(5, 7)}/${k.slice(8, 10)}`;
  return `${md(b.period_start)} ~ ${md(b.period_end)} · ${b.start_time.slice(0, 5)} ~ ${b.end_time.slice(0, 5)}`;
}
