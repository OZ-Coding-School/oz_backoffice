import { describe, expect, it } from "vitest";

import {
  addDays,
  dayStartMs,
  daySegment,
  isoWeekday,
  occurrences,
  periodLabel,
  weekStart,
  weekTitle,
  type UnavailablePeriod,
} from "./schedule";

function period(overrides: Partial<UnavailablePeriod>): UnavailablePeriod {
  return {
    id: "p1",
    mentor_id: "m1",
    repeat: "ONCE",
    starts_at: "2026-11-23T10:00:00Z", // 11/23(월) 19:00 KST
    ends_at: "2026-11-23T12:00:00Z",
    all_day: false,
    weekdays: [],
    repeat_until: null,
    category: null,
    reason: null,
    ...overrides,
  };
}

const WEEK_FROM = dayStartMs("2026-11-23");
const WEEK_TO = dayStartMs("2026-11-30");
const kst = (ms: number) => new Date(ms + 9 * 3_600_000).toISOString().slice(0, 16);

describe("주 계산 (KST)", () => {
  it("월요일 시작, 요일, 제목", () => {
    expect(isoWeekday("2026-11-23")).toBe(1);
    expect(isoWeekday("2026-11-29")).toBe(7);
    expect(weekStart("2026-11-26")).toBe("2026-11-23");
    expect(weekStart("2026-11-29")).toBe("2026-11-23");
    expect(addDays("2026-11-30", 1)).toBe("2026-12-01");
    expect(weekTitle("2026-11-23")).toBe("11월 23일 ~ 29일");
    expect(weekTitle("2026-11-30")).toBe("11월 30일 ~ 12월 6일");
  });
});

describe("불가 시간 회차 (백엔드 occurrences와 같은 규칙)", () => {
  it("한 번: 그 주와 겹치면 하나", () => {
    expect(occurrences(period({}), WEEK_FROM, WEEK_TO).map(([s]) => kst(s))).toEqual(["2026-11-23T19:00"]);
    expect(occurrences(period({}), dayStartMs("2026-11-30"), dayStartMs("2026-12-07"))).toEqual([]);
  });

  it("매주 화·목, 반복 종료일까지 (그날 시작 회차 포함)", () => {
    const weekly = period({
      repeat: "WEEKLY",
      starts_at: "2026-11-03T00:00:00Z", // 11/3(화) 09:00 KST
      ends_at: "2026-11-03T03:00:00Z",
      weekdays: [2, 4],
      repeat_until: "2026-11-26",
    });
    expect(occurrences(weekly, WEEK_FROM, WEEK_TO).map(([s, e]) => [kst(s), kst(e)])).toEqual([
      ["2026-11-24T09:00", "2026-11-24T12:00"],
      ["2026-11-26T09:00", "2026-11-26T12:00"],
    ]);
  });

  it("매일 23:00~다음 날 01:00: 주 앞날 밤에 시작한 회차도 걸치고, 하루 칸으로 나눈다", () => {
    const daily = period({ repeat: "DAILY", starts_at: "2026-11-01T14:00:00Z", ends_at: "2026-11-01T16:00:00Z" });
    const found = occurrences(daily, WEEK_FROM, WEEK_TO);
    expect(kst(found[0]![0])).toBe("2026-11-22T23:00"); // 일요일 밤 회차가 월요일 00~01시에 걸친다
    expect(found).toHaveLength(8);
    expect(daySegment(found[0]!, "2026-11-23")).toEqual([0, 60]);
    expect(daySegment(found[1]!, "2026-11-23")).toEqual([1380, 1440]);
    expect(daySegment(found[1]!, "2026-11-24")).toEqual([0, 60]);
  });

  it("목록 문구", () => {
    expect(periodLabel(period({}))).toBe("11/23(월) 19:00~21:00");
    expect(
      periodLabel(
        period({
          repeat: "WEEKLY",
          starts_at: "2026-11-03T00:00:00Z",
          ends_at: "2026-11-03T03:00:00Z",
          weekdays: [5, 2, 3, 4],
          repeat_until: "2026-12-31",
        }),
      ),
    ).toBe("매주 화·수·목·금 09:00~12:00 · 12/31까지");
    expect(
      periodLabel(period({ repeat: "DAILY", starts_at: "2026-11-01T14:00:00Z", ends_at: "2026-11-01T16:00:00Z" })),
    ).toBe("매일 23:00~다음 날 01:00");
    expect(
      periodLabel(period({ all_day: true, starts_at: "2026-12-23T15:00:00Z", ends_at: "2026-12-26T15:00:00Z" })),
    ).toBe("12/24(목) 하루 종일 ~ 12/26(토)");
    expect(periodLabel(period({ starts_at: "2026-11-23T13:00:00Z", ends_at: "2026-11-23T15:00:00Z" }))).toBe(
      "11/23(월) 22:00~24:00",
    );
  });
});
