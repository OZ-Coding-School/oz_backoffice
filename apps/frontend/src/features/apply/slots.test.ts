import { expertiseChips } from "./api";
import { blockReason } from "./gate";
import { durationOptions, monthRanges, startTimes } from "./slots";

const cohort = {
  enrollment: { student_id: "st12", cohort_id: "c12" },
  readOnly: false,
} as Parameters<typeof blockReason>[0]["cohort"];
const settings = {
  cohort_id: "c12",
  allow_1_on_1: true,
  allow_team_mentoring: false,
  allowed_duration: 60,
  min_lead_hours: 24,
  max_pending_requests: 3,
};
const account = (remaining: number, expired = false) => ({
  id: "a1",
  owner_type: "STUDENT" as const,
  owner_id: "st12",
  owner_name: "가수강",
  valid_from: "2026-10-01",
  valid_until: "2027-03-31",
  is_expired: expired,
  total_minutes: 180,
  held_minutes: 0,
  used_minutes: 0,
  remaining_minutes: remaining,
});

describe("신청 가능 시각 (F30)", () => {
  it("구간 안에서 진행 시간으로 시작할 수 있는 30분 경계 시각만, KST 날짜별로", () => {
    const byDay = startTimes(
      [
        { starts_at: "2026-11-20T01:10:00Z", ends_at: "2026-11-20T03:00:00Z" }, // 10:10~12:00 KST
        { starts_at: "2026-11-20T14:30:00Z", ends_at: "2026-11-20T16:00:00Z" }, // 23:30~다음날 01:00 KST
      ],
      60,
    );
    expect(byDay.get("2026-11-20")).toEqual([
      "2026-11-20T01:30:00.000Z",
      "2026-11-20T02:00:00.000Z",
      "2026-11-20T14:30:00.000Z",
    ]);
    expect(byDay.get("2026-11-21")).toEqual(["2026-11-20T15:00:00.000Z"]);
    expect(startTimes([{ starts_at: "2026-11-20T01:00:00Z", ends_at: "2026-11-20T01:30:00Z" }], 60).size).toBe(0);
  });

  it("진행 시간 선택지: 진행 단위 배수, 120분까지, 남은 시간 이하", () => {
    expect(durationOptions(30, 180)).toEqual([30, 60, 90, 120]);
    expect(durationOptions(60, 90)).toEqual([60]);
    expect(durationOptions(60, 30)).toEqual([]);
  });

  it("보이는 달의 조회 범위는 오늘~60일과 겹치는 부분, 31일씩 나눈다", () => {
    const today = new Date("2026-11-19T03:00:00Z");
    expect(monthRanges(new Date("2026-11-01T00:00:00+09:00"), today)).toEqual([["2026-11-19", "2026-11-30"]]);
    expect(monthRanges(new Date("2026-12-01T00:00:00+09:00"), today)).toEqual([["2026-12-01", "2026-12-31"]]);
    expect(monthRanges(new Date("2027-01-01T00:00:00+09:00"), today)).toEqual([["2027-01-01", "2027-01-18"]]);
    expect(monthRanges(new Date("2027-02-01T00:00:00+09:00"), today)).toEqual([]);
  });
});

describe("신청 첫머리 판정 (F28·F30)", () => {
  it("수강 등록 없음·읽기 전용·1:1 불가·남은 시간 없음", () => {
    expect(blockReason({ cohort: null, settings, account: account(120) })).toBe("no_enrollment");
    expect(blockReason({ cohort: { ...cohort!, readOnly: true }, settings, account: account(120) })).toBe("read_only");
    expect(blockReason({ cohort, settings: { ...settings, allow_1_on_1: false }, account: account(120) })).toBe(
      "one_on_one_not_allowed",
    );
    expect(blockReason({ cohort, settings, account: undefined })).toBe("no_time");
    expect(blockReason({ cohort, settings, account: account(120, true) })).toBe("no_time");
    expect(blockReason({ cohort, settings, account: account(59) })).toBe("no_time");
    expect(blockReason({ cohort, settings, account: account(60) })).toBeNull();
  });

  it("전문 분야는 쉼표로 나눈다", () => {
    expect(expertiseChips(" Python, Django ,, 이력서 ")).toEqual(["Python", "Django", "이력서"]);
    expect(expertiseChips(null)).toEqual([]);
  });
});
