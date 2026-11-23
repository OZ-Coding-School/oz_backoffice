import { ENROLLMENTS } from "@/features/auth/test-utils";

import { activeCohort, cohortLabel, type Enrollment } from "./api";
import { bottomTabLayout, currentNavItem, memberNav, navItems, showBottomTabs, type MemberNavGroup } from "./nav";

const base = ENROLLMENTS[0] as Enrollment;
const past: Enrollment = { ...base, cohort_id: "c3", cohort_number: 3, start_date: "2021-03-01", status: "COMPLETED" };

describe("활성 기수 (F27)", () => {
  it("수강 중인 기수를 쓴다", () => {
    expect(activeCohort([past, base])).toEqual({ enrollment: base, readOnly: false });
  });

  it("수강 중이 없으면 가장 최근 기수를 읽기 전용으로 쓴다", () => {
    const dropped = { ...base, status: "DROPPED" as const };
    expect(activeCohort([past, dropped])).toEqual({ enrollment: dropped, readOnly: true });
  });

  it("등록이 없으면 없다", () => {
    expect(activeCohort([])).toBeNull();
  });

  it("과정 이름과 기수로 보여 준다", () => {
    expect(cohortLabel(base)).toBe("초격차 백엔드 12기");
  });
});

describe("회원 메뉴 (F27)", () => {
  it("수강생은 만든 메뉴를 모두 보고, 멘토는 홈·받은 신청·채팅이라 하단 탭이 있다", () => {
    expect(navItems(memberNav("STUDENT")).map((i) => i.label)).toEqual([
      "홈",
      "신청 내역",
      "진행 기록",
      "채팅",
      "시간 지급·차감 내역",
      "내 정보",
    ]);
    expect(navItems(memberNav("STUDENT", { apply: true })).map((i) => i.label)).toEqual([
      "홈",
      "멘토링 신청",
      "신청 내역",
      "진행 기록",
      "채팅",
      "시간 지급·차감 내역",
      "내 정보",
    ]);
    expect(showBottomTabs(memberNav("STUDENT"))).toBe(true);
    expect(navItems(memberNav("MENTOR")).map((i) => i.label)).toEqual(["홈", "받은 신청", "채팅"]); // F40·F43
    expect(showBottomTabs(memberNav("MENTOR"))).toBe(true);
  });

  it("메뉴가 2개 이상이면 하단 탭을 보여 주고, 하위 경로는 가장 긴 메뉴로 찾는다", () => {
    const icon = memberNav("STUDENT")[0]!.items[0]!.icon;
    const groups: MemberNavGroup[] = [
      { items: [{ to: "/", label: "홈", shortLabel: "홈", icon }] },
      { title: "멘토링", items: [{ to: "/mentoring/requests", label: "신청 내역", shortLabel: "신청", icon }] },
    ];
    expect(showBottomTabs(groups)).toBe(true);
    expect(currentNavItem(groups, "/mentoring/requests/r1")?.label).toBe("신청 내역");
    expect(currentNavItem(groups, "/")?.label).toBe("홈");
    expect(currentNavItem(groups, "/unknown")).toBeUndefined();
  });
});

describe("하단 탭 더보기 (F36)", () => {
  it("메뉴가 5개 이하면 모두 탭이다", () => {
    const layout = bottomTabLayout(memberNav("MENTOR"));
    expect(layout.tabs.map((i) => i.shortLabel)).toEqual(["홈", "받은 신청", "채팅"]);
    expect(layout.more).toEqual([]);
  });

  it("팀이 있으면 '내 팀'이 진행 기록 다음에 들어간다 (F39)", () => {
    expect(navItems(memberNav("STUDENT", { apply: true, team: true })).map((i) => i.label)).toEqual([
      "홈",
      "멘토링 신청",
      "신청 내역",
      "진행 기록",
      "내 팀",
      "채팅",
      "시간 지급·차감 내역",
      "내 정보",
    ]);
  });

  it("넘으면 홈·신청·진행 기록·신청 내역 + 나머지는 그룹째 더보기", () => {
    const layout = bottomTabLayout(memberNav("STUDENT", { apply: true }));
    expect(layout.tabs.map((i) => i.shortLabel)).toEqual(["홈", "신청", "진행 기록", "신청 내역"]);
    expect(layout.more.map((g) => [g.title, g.items.map((i) => i.label)])).toEqual([
      ["멘토링", ["채팅", "시간 지급·차감 내역"]],
      ["내 공간", ["내 정보"]],
    ]);
  });
});
