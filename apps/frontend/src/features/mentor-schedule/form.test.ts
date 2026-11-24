import { describe, expect, it } from "vitest";

import { bodyOf, emptyForm, formOf, unavailableSchema, type UnavailableForm } from "./form";

const base: UnavailableForm = { ...emptyForm("2026-11-24"), startTime: "09:00", endTime: "12:00" };

describe("불가 시간 입력 → API 본문 (F53)", () => {
  it("매주: 요일 정렬, KST 시각, 반복 종료", () => {
    expect(
      bodyOf({
        ...base,
        repeat: "WEEKLY",
        weekdays: [5, 2],
        repeatUntil: "2026-12-31",
        category: " 본업 ",
        reason: "",
      }),
    ).toEqual({
      repeat: "WEEKLY",
      all_day: false,
      starts_at: "2026-11-24T00:00:00.000Z",
      ends_at: "2026-11-24T03:00:00.000Z",
      weekdays: [2, 5],
      repeat_until: "2026-12-31",
      category: "본업",
      reason: null,
    });
  });

  it("한 번 자정 넘김: 종료 날짜를 다음 날로", () => {
    const body = bodyOf({ ...base, startTime: "23:00", endDate: "2026-11-25", endTime: "01:00" });
    expect([body.starts_at, body.ends_at, body.repeat_until]).toEqual([
      "2026-11-24T14:00:00.000Z",
      "2026-11-24T16:00:00.000Z",
      null,
    ]);
  });

  it("하루 종일은 날짜로 보낸다", () => {
    expect(bodyOf({ ...base, allDay: true, startDate: "2026-12-24", endDate: "2026-12-26" })).toMatchObject({
      repeat: "ONCE",
      all_day: true,
      start_date: "2026-12-24",
      end_date: "2026-12-26",
    });
  });

  it("검사: 종료가 시작보다 앞, 24시간 넘음, 매주 요일 없음, 반복 종료가 시작보다 앞", () => {
    const issue = (v: UnavailableForm) => unavailableSchema.safeParse(v).error?.issues[0]?.message;
    expect(issue({ ...base, endTime: "08:00" })).toBe("종료는 시작보다 뒤여야 해요.");
    expect(issue({ ...base, endDate: "2026-11-25", endTime: "10:00" })).toBe("한 번에 24시간까지 등록할 수 있어요.");
    expect(issue({ ...base, repeat: "WEEKLY" })).toBe("요일을 하나 이상 골라 주세요.");
    expect(issue({ ...base, repeat: "DAILY", repeatUntil: "2026-11-20" })).toBe(
      "반복 종료는 시작 날짜와 같거나 뒤여야 해요.",
    );
    expect(unavailableSchema.safeParse({ ...base, endDate: "2026-11-25", endTime: "09:00" }).success).toBe(true);
  });

  it("등록한 하루 종일을 고치면 마지막 날은 끝 직전 날", () => {
    const form = formOf({
      id: "p",
      mentor_id: "m",
      repeat: "ONCE",
      all_day: true,
      starts_at: "2026-12-23T15:00:00Z",
      ends_at: "2026-12-26T15:00:00Z",
      weekdays: [],
      repeat_until: null,
      category: "휴가",
      reason: null,
    });
    expect([form.startDate, form.endDate, form.category]).toEqual(["2026-12-24", "2026-12-26", "휴가"]);
  });
});
