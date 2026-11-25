import type { StaffOptions } from "@/features/auth/staff-api";

import type { Employee } from "./api";
import type { EmployeeFormValues } from "./form";
import { payload } from "./form";
import { groupEmployees } from "./groups";

const OPTIONS: StaffOptions = {
  departments: [
    { id: "d1", name: "교육운영본부" },
    { id: "d2", name: "경영지원본부" },
  ],
  teams: [
    { id: "t1", department_id: "d1", name: "교육 2팀" },
    { id: "t2", department_id: "d1", name: "교육 1팀" },
  ],
  positions: [
    { id: "p1", name: "운영 매니저", assignment_scope: "COURSE" },
    { id: "p2", name: "조교", assignment_scope: "COHORT" },
    { id: "p3", name: "인사 담당", assignment_scope: null },
  ],
  employment_types: ["REGULAR", "CONTRACT"],
  bootcamps: [{ id: "b1", name: "백엔드 부트캠프", code: "BE", team_id: "t1" }],
  cohorts: [],
};

function employee(id: string, name: string, department: string, team: string | null): Employee {
  return {
    id,
    user: { id: `u-${id}`, email: `${id}@nextrunners.co.kr`, name },
    department_id: department,
    team_id: team,
    position_id: "p1",
    employment_type: "REGULAR",
    assignments: [],
    is_super_admin: false,
    data_scope: "ASSIGNED",
  };
}

const EMPLOYEES = [
  employee("e1", "한팀장", "d1", null),
  employee("e2", "이조교", "d1", "t1"),
  employee("e3", "김운영", "d1", "t2"),
  employee("e4", "박인사", "d2", null),
  employee("e5", "가운영", "d1", "t2"),
];

describe("부서 › 팀 묶기 (F67)", () => {
  it("부서·팀·직원은 이름순, 팀 없음은 부서 맨 아래", () => {
    const groups = groupEmployees(EMPLOYEES, OPTIONS);
    expect(groups.map((d) => [d.name, d.count])).toEqual([
      ["경영지원본부", 1],
      ["교육운영본부", 4],
    ]);
    const edu = groups[1];
    expect(edu?.teams.map((t) => [t.name, t.employees.map((e) => e.user?.name)])).toEqual([
      ["교육 1팀", ["가운영", "김운영"]],
      ["교육 2팀", ["이조교"]],
      ["팀 없음", ["한팀장"]],
    ]);
  });

  it("검색어는 이름·이메일에서 찾고, 맞는 직원이 없는 묶음은 뺀다", () => {
    expect(groupEmployees(EMPLOYEES, OPTIONS, "운영").map((d) => d.count)).toEqual([2]);
    expect(groupEmployees(EMPLOYEES, OPTIONS, "E4@NEXT").map((d) => d.name)).toEqual(["경영지원본부"]);
    expect(groupEmployees(EMPLOYEES, OPTIONS, "없는 사람")).toEqual([]);
  });
});

describe("직원 수정 본문 (A89·A90)", () => {
  const initial: EmployeeFormValues = {
    department_id: "d1",
    team_id: "t1",
    position_id: "p1",
    employment_type: "REGULAR",
    bootcamp_ids: ["b1"],
    cohort_bootcamp_id: "",
    cohort_id: "",
    is_super_admin: false,
  };
  const all = { org: true, assign: true, superAdmin: true };

  it("바뀐 항목만 보내고, 팀 없음은 null", () => {
    expect(payload(OPTIONS, initial, initial, all)).toEqual({});
    expect(payload(OPTIONS, initial, { ...initial, team_id: "none", is_super_admin: true }, all)).toEqual({
      team_id: null,
      is_super_admin: true,
    });
  });

  it("직위를 바꾸면 새 담당 방식으로 담당을 통째로 보낸다", () => {
    const changed = { ...initial, position_id: "p2", bootcamp_ids: [], cohort_bootcamp_id: "b1", cohort_id: "c12" };
    expect(payload(OPTIONS, initial, changed, all)).toEqual({
      position_id: "p2",
      bootcamp_ids: [],
      cohort_ids: ["c12"],
    });
  });

  it("권한이 없는 항목은 바뀌어도 보내지 않는다", () => {
    const changed = { ...initial, employment_type: "CONTRACT", bootcamp_ids: [], is_super_admin: true };
    expect(payload(OPTIONS, initial, changed, { org: false, assign: true, superAdmin: false })).toEqual({
      bootcamp_ids: [],
      cohort_ids: [],
    });
  });
});
