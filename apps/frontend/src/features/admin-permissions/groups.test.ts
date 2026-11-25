import type { PermissionDef } from "./api";
import { buildGroups, diff, orderedCodes, toggle } from "./groups";

function def(
  code: string,
  entity: string,
  action: string,
  area = "멘토링",
  requires: string | null = null,
): PermissionDef {
  return { code, area, entity, action, description: "", cohort_bound: true, requires };
}

const DEFS: PermissionDef[] = [
  def("org.department.read", "부서·팀", "조회", "조직"),
  def("org.department.manage", "부서·팀", "관리", "조직", "org.department.read"),
  def("mentoring.request.read", "신청·세션", "조회"),
  def("mentoring.request.cancel", "신청·세션", "취소", "멘토링", "mentoring.request.read"),
  def("mentoring.chat.read", "채팅", "조회"),
];

describe("권한 그룹 (A86)", () => {
  it("영역별로 엔터티 행을 만든다: 조회 칸과 관리·동작 칸", () => {
    const groups = buildGroups(DEFS);
    expect(groups.map((g) => g.area)).toEqual(["조직", "멘토링"]);
    const mentoring = groups[1];
    expect(mentoring?.codes).toHaveLength(3);
    expect(mentoring?.rows.map((r) => [r.entity, r.read?.code, r.action?.code ?? null])).toEqual([
      ["신청·세션", "mentoring.request.read", "mentoring.request.cancel"],
      ["채팅", "mentoring.chat.read", null],
    ]);
  });

  it("관리를 켜면 조회도 켜고, 조회를 끄면 관리도 끈다", () => {
    const manage = DEFS[1];
    const read = DEFS[0];
    if (!manage || !read) throw new Error("정의 없음");
    const on = toggle(new Set(), manage, true, DEFS);
    expect([...on].sort()).toEqual(["org.department.manage", "org.department.read"]);
    expect([...toggle(on, read, false, DEFS)]).toEqual([]);
    expect([...toggle(on, manage, false, DEFS)]).toEqual(["org.department.read"]);
  });

  it("차이와 저장 본문은 정의 순서", () => {
    const before = new Set(["mentoring.chat.read", "org.department.read"]);
    const after = new Set(["mentoring.request.read", "org.department.read"]);
    expect(diff(before, after, DEFS)).toEqual([
      { code: "mentoring.request.read", label: "신청·세션 · 조회", on: true },
      { code: "mentoring.chat.read", label: "채팅 · 조회", on: false },
    ]);
    expect(orderedCodes(after, DEFS)).toEqual(["org.department.read", "mentoring.request.read"]);
  });
});
