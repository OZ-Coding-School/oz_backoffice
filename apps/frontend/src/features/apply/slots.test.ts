import { expertiseChips } from "./api";
import { allowedKinds, blockReason } from "./gate";
import { durationOptions, kstDateKey, monthRanges, startTimes } from "./slots";
import { makeStudentTeam } from "./team-fixture";

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

  it("TZDate로 받은 달도 브라우저 시간대와 무관하게 KST 날짜로 읽는다", async () => {
    const { TZDate } = await import("@date-fns/tz");
    const month = new TZDate(2026, 10, 1, "Asia/Seoul"); // 11/1 00:00 KST
    expect(kstDateKey(month)).toBe("2026-11-01");
    expect(monthRanges(month, new Date("2026-11-19T03:00:00Z"))).toEqual([["2026-11-19", "2026-11-30"]]);
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

describe("신청 첫머리 판정 (F28·F30·F31)", () => {
  const one = (o: Partial<Parameters<typeof blockReason>[0]>) =>
    blockReason({ cohort, settings, kind: "one", account: account(120), ...o });
  it("1:1: 수강 등록 없음·읽기 전용·1:1 불가·남은 시간 없음", () => {
    expect(one({ cohort: null })).toBe("no_enrollment");
    expect(one({ cohort: { ...cohort!, readOnly: true } })).toBe("read_only");
    expect(one({ settings: { ...settings, allow_1_on_1: false, allow_team_mentoring: true } })).toBe(
      "one_on_one_not_allowed",
    );
    expect(one({ settings: { ...settings, allow_1_on_1: false } })).toBe("not_allowed");
    expect(one({ account: undefined })).toBe("no_time");
    expect(one({ account: account(120, true) })).toBe("no_time");
    expect(one({ account: account(59) })).toBe("no_time");
    expect(one({ account: account(60) })).toBeNull();
  });

  it("팀: 팀 불가·팀 없음·팀 시간 없음·담당 멘토가 신청을 안 받음", () => {
    const teamSettings = { ...settings, allow_team_mentoring: true };
    const team = makeStudentTeam();
    const teamCase = (o: Partial<Parameters<typeof blockReason>[0]>) =>
      blockReason({
        cohort,
        settings: teamSettings,
        kind: "team",
        account: account(120),
        team,
        teamMentor: { accepting_requests: true },
        ...o,
      });
    expect(teamCase({ settings })).toBe("team_not_allowed");
    expect(teamCase({ team: undefined })).toBe("no_team");
    expect(teamCase({ account: account(30) })).toBe("team_no_time");
    expect(teamCase({ teamMentor: { accepting_requests: false } })).toBe("mentor_not_accepting");
    expect(teamCase({})).toBeNull();
    expect(allowedKinds(teamSettings)).toEqual(["team", "one"]);
    expect(allowedKinds(undefined)).toEqual([]);
  });

  it("전문 분야는 쉼표로 나눈다", () => {
    expect(expertiseChips(" Python, Django ,, 이력서 ")).toEqual(["Python", "Django", "이력서"]);
    expect(expertiseChips(null)).toEqual([]);
  });
});
