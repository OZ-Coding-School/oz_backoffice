import { describe, expect, it } from "vitest";

import { makeSession } from "@/features/sessions/test-utils";

import { dayEvents, weekSegments, type CalendarEvent } from "./calendar";
import { addMonths, monthGridDays, monthTitle, weekDays, type UnavailablePeriod } from "./schedule";

const base: UnavailablePeriod = {
  id: "p1",
  mentor_id: "m1",
  repeat: "WEEKLY",
  starts_at: "2026-11-03T00:00:00Z", // 화 09:00 KST
  ends_at: "2026-11-03T03:00:00Z",
  all_day: false,
  weekdays: [2, 3, 4, 5],
  repeat_until: "2026-12-31",
  category: "본업",
  reason: null,
};
const DAILY: UnavailablePeriod = {
  ...base,
  id: "p2",
  repeat: "DAILY",
  starts_at: "2026-11-26T13:00:00Z", // 22:00 KST
  ends_at: "2026-11-26T15:00:00Z",
  weekdays: [],
  category: "휴식",
};
const VACATION: UnavailablePeriod = {
  ...base,
  id: "p3",
  repeat: "ONCE",
  all_day: true,
  starts_at: "2026-11-24T15:00:00Z", // 11/25 ~ 11/26 하루 종일
  ends_at: "2026-11-26T15:00:00Z",
  weekdays: [],
  repeat_until: null,
  category: "휴가",
};

describe("달 도우미 (F89)", () => {
  it("6주 격자는 1일이 든 주의 월요일부터", () => {
    const days = monthGridDays("2026-11");
    expect([days[0], days[6], days.at(-1), days.length]).toEqual(["2026-10-26", "2026-11-01", "2026-12-06", 42]);
    expect([addMonths("2026-12", 1), addMonths("2026-01", -1), monthTitle("2026-03")]).toEqual([
      "2027-01",
      "2025-12",
      "2026년 3월",
    ]);
  });
});

describe("월 달력 일정 (F89)", () => {
  it("시각이 있는 회차는 시작한 날, 하루 종일은 걸친 날마다. 세션은 그날", () => {
    const session = makeSession({ starts_at: "2026-11-25T10:00:00Z", ends_at: "2026-11-25T11:00:00Z" });
    const events = dayEvents("2026-11-25", [base, DAILY, VACATION], [session]);
    expect(events.map((e) => [e.time, e.label, e.kind])).toEqual([
      ["하루 종일", "휴가", "personal"],
      ["9:00", "본업 · 매주", "personal"],
      ["19:00", "가수강 · 1:1", "session"],
    ]);
    expect(dayEvents("2026-11-26", [VACATION, DAILY], []).map((e) => e.time)).toEqual(["하루 종일", "22:00"]);
  });

  it("같은 개인 일정은 이웃한 날끼리 한 막대, 이어진 막대는 같은 줄, 넘치면 칸마다 숨은 수", () => {
    const week = weekDays("2026-11-23");
    const session = makeSession({ starts_at: "2026-11-27T07:00:00Z", ends_at: "2026-11-27T08:00:00Z" });
    const once: UnavailablePeriod = {
      ...base,
      id: "p4",
      repeat: "ONCE",
      starts_at: "2026-11-27T05:00:00Z",
      ends_at: "2026-11-27T09:00:00Z",
      weekdays: [],
      repeat_until: null,
      category: "개인 일정",
    };
    const columns = week.map((d) => dayEvents(d, [base, DAILY, once], [session]));
    const { segments, hidden } = weekSegments(columns);
    const view = (e: CalendarEvent) => e.label;
    expect(segments.map((s) => [view(s.event), s.from, s.to, s.lane])).toEqual([
      ["본업 · 매주", 1, 4, 0],
      ["휴식 · 매일", 3, 6, 1],
      ["개인 일정", 4, 4, 2],
      ["가수강 · 1:1", 4, 4, 3],
    ]);
    expect(hidden).toEqual([0, 0, 0, 0, 1, 0, 0]);
  });
});
