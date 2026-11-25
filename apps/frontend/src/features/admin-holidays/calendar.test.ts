import { daysInMonth, isDateKey, longLabel, monthCells, shortLabel, weekday } from "./calendar";

describe("공휴일 달력 날짜 계산", () => {
  it("요일과 말일 (윤년 포함)", () => {
    expect(weekday("2026-06-05")).toBe(5); // 금
    expect(weekday("2026-11-01")).toBe(0); // 일
    expect(daysInMonth(2028, 2)).toBe(29);
    expect(daysInMonth(2026, 2)).toBe(28);
  });

  it("한 달 칸은 1일 요일만큼 비우고 시작한다", () => {
    const cells = monthCells(2026, 7); // 7/1 수요일
    expect(cells.slice(0, 4)).toEqual([null, null, null, "2026-07-01"]);
    expect(cells.at(-1)).toBe("2026-07-31");
    expect(monthCells(2026, 11)[0]).toBe("2026-11-01"); // 일요일 시작
  });

  it("주소의 날짜 검증과 표시", () => {
    expect(isDateKey("2026-02-28")).toBe(true);
    expect(isDateKey("2026-02-29")).toBe(false);
    expect(isDateKey("2026-6-5")).toBe(false);
    expect(longLabel("2026-06-05")).toBe("2026년 6월 5일 (금)");
    expect(shortLabel("2026-12-31")).toBe("12/31 (목)");
  });
});
