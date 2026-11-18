import { departmentLabels, fromTargetValue, targetOptions, toTargetValue, type StaffOptions } from "./staff-api";

const OPTIONS: StaffOptions = {
  departments: [
    { id: "d1", parent_id: null, name: "교육본부" },
    { id: "d2", parent_id: "d1", name: "교육운영팀" },
    { id: "d3", parent_id: null, name: "경영지원팀" },
  ],
  positions: [],
  employment_types: ["REGULAR"],
  staff_roles: ["MANAGER", "ASSISTANT"],
  bootcamps: [{ id: "b1", name: "백엔드 부트캠프", code: "BE" }],
  cohorts: [
    {
      id: "c9",
      bootcamp_id: "b1",
      cohort_number: 9,
      status: "ONGOING",
      start_date: "2026-01-01",
      end_date: "2026-06-30",
    },
  ],
};

describe("운영진 정보 입력 보기", () => {
  it("부서는 '상위 › 하위' 경로로 보여 주고 경로 순서로 정렬한다", () => {
    expect(departmentLabels(OPTIONS.departments).map((d) => d.label)).toEqual([
      "경영지원팀",
      "교육본부",
      "교육본부 › 교육운영팀",
    ]);
  });

  it("운영 매니저는 과정 전체와 기수, 조교는 기수만 고른다", () => {
    expect(targetOptions(OPTIONS, "MANAGER").map((t) => t.label)).toEqual([
      "백엔드 부트캠프 (과정 전체)",
      "백엔드 부트캠프 9기",
    ]);
    expect(targetOptions(OPTIONS, "ASSISTANT").map((t) => t.label)).toEqual(["백엔드 부트캠프 9기"]);
  });

  it("담당 대상 값을 API 형식과 서로 바꾼다", () => {
    expect(fromTargetValue("bootcamp:b1")).toEqual({ bootcamp_id: "b1", cohort_id: null });
    expect(fromTargetValue("cohort:c9")).toEqual({ bootcamp_id: null, cohort_id: "c9" });
    expect(toTargetValue({ bootcamp_id: null, cohort_id: "c9" })).toBe("cohort:c9");
  });
});
