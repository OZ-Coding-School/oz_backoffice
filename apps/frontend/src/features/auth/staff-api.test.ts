import {
  assignmentLabel,
  bootcampCohorts,
  NO_TEAM,
  scopeOf,
  teamBootcamps,
  teamsOf,
  type StaffOptions,
} from "./staff-api";

const cohort = (id: string, bootcamp_id: string, cohort_number: number) => ({
  id,
  bootcamp_id,
  cohort_number,
  status: "ONGOING" as const,
  start_date: "2026-01-01",
  end_date: "2026-06-30",
});

const OPTIONS: StaffOptions = {
  departments: [{ id: "d1", name: "교육운영본부" }],
  teams: [
    { id: "t2", department_id: "d1", name: "교육 2팀" },
    { id: "t1", department_id: "d1", name: "교육 1팀" },
    { id: "tx", department_id: "d9", name: "다른 본부 팀" },
  ],
  positions: [
    { id: "p1", name: "운영 매니저", assignment_scope: "COURSE" },
    { id: "p2", name: "조교", assignment_scope: "COHORT" },
    { id: "p3", name: "인턴", assignment_scope: null },
  ],
  employment_types: ["REGULAR"],
  bootcamps: [
    { id: "b2", name: "프론트엔드 부트캠프", code: "FE", team_id: "t1" },
    { id: "b1", name: "백엔드 부트캠프", code: "BE", team_id: "t1" },
    { id: "b3", name: "디자인", code: "UX", team_id: "t2" },
  ],
  cohorts: [cohort("c10", "b1", 10), cohort("c9", "b1", 9), cohort("f3", "b2", 3)],
};

describe("운영진 정보 입력 선택지", () => {
  it("고른 부서의 팀만 이름순으로 보여 준다", () => {
    expect(teamsOf(OPTIONS, "d1").map((t) => t.name)).toEqual(["교육 1팀", "교육 2팀"]);
  });

  it("팀이 담당하는 과정만 고를 수 있고, 부서 직속이면 과정이 없다", () => {
    expect(teamBootcamps(OPTIONS, "t1").map((b) => b.name)).toEqual(["백엔드 부트캠프", "프론트엔드 부트캠프"]);
    expect(teamBootcamps(OPTIONS, NO_TEAM)).toEqual([]);
    expect(teamBootcamps(OPTIONS, "")).toEqual([]);
  });

  it("과정의 기수를 회차순으로 보여 준다", () => {
    expect(bootcampCohorts(OPTIONS, "b1").map((c) => c.cohort_number)).toEqual([9, 10]);
  });

  it("직위의 담당 방식과 담당 표시 이름", () => {
    expect([scopeOf(OPTIONS, "p1"), scopeOf(OPTIONS, "p2"), scopeOf(OPTIONS, "p3")]).toEqual([
      "COURSE",
      "COHORT",
      null,
    ]);
    expect(assignmentLabel(OPTIONS, { bootcamp_id: "b1", cohort_id: null })).toBe("백엔드 부트캠프");
    expect(assignmentLabel(OPTIONS, { bootcamp_id: null, cohort_id: "c9" })).toBe("백엔드 부트캠프 9기");
    expect(assignmentLabel(OPTIONS, { bootcamp_id: null, cohort_id: "gone" })).toBeNull();
  });
});
