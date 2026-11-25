import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { PermissionDef, Position } from "./api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: true });

function def(
  code: string,
  area: string,
  entity: string,
  action: string,
  requires: string | null = null,
): PermissionDef {
  return { code, area, entity, action, description: `${entity} 설명`, cohort_bound: area !== "조직", requires };
}

const DEFS: PermissionDef[] = [
  def("org.department.read", "조직", "부서·팀", "조회"),
  def("org.department.manage", "조직", "부서·팀", "관리", "org.department.read"),
  def("academy.roster.read", "학사", "수강생 명단", "조회"),
  def("academy.roster.sync", "학사", "수강생 명단", "동기화", "academy.roster.read"),
  def("mentoring.chat.read", "멘토링", "채팅", "조회"),
];

function position(id: string, name: string, permissions: string[], extra: Partial<Position> = {}): Position {
  return {
    id,
    name,
    priority: 1,
    assignment_scope: "COURSE",
    data_scope: "ASSIGNED",
    permissions,
    employee_count: 6,
    ...extra,
  };
}

const MANAGER = position("p1", "운영 매니저", ["academy.roster.read"]);
const LEAD = position("p2", "팀리드", ["org.department.read"], { data_scope: "ALL", employee_count: 2 });

function access(codes: string[]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [],
  };
}

function mockApi({ codes = ["access.role.read", "access.role.manage"], fail = false } = {}) {
  const calls: { id: string; body: unknown }[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/admin/positions"), () => HttpResponse.json([MANAGER, LEAD])),
    http.get(apiUrl("/api/v1/admin/permissions"), () => HttpResponse.json(DEFS)),
    http.put(apiUrl("/api/v1/admin/positions/{position_id}/permissions"), async ({ params, request }) => {
      const body = (await request.json()) as { permissions: string[] };
      calls.push({ id: String(params.position_id), body });
      if (fail) {
        return HttpResponse.json(
          { error: { code: "permission_requires_read", message: "조회와 함께" } },
          { status: 422 },
        );
      }
      return HttpResponse.json({ ...MANAGER, permissions: body.permissions });
    }),
  );
  return calls;
}

describe("조직 설정 > 권한 (FE-15d)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("직위를 고르고 그룹을 접고 펼친다", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/org/permissions");
    const section = await screen.findByRole("region", { name: "운영 매니저 권한" });
    expect(within(section).getByText("데이터 범위: 담당 과정·기수만")).toBeInTheDocument();
    expect(within(section).getByRole("checkbox", { name: "수강생 명단 조회" })).toBeChecked();
    expect(within(section).getByText("변경 사항 없음")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(within(section).getByRole("button", { name: /조직/ }));
    expect(within(section).queryByRole("checkbox", { name: "부서·팀 조회" })).not.toBeInTheDocument();
    await user.click(within(section).getByRole("button", { name: "모두 펼치기" }));
    expect(within(section).getByRole("checkbox", { name: "부서·팀 조회" })).toBeInTheDocument();

    await user.click(within(screen.getByRole("navigation", { name: "직위" })).getByRole("button", { name: /팀리드/ }));
    expect(await screen.findByRole("region", { name: "팀리드 권한" })).toBeInTheDocument();
    expect(router.state.location.search).toEqual({ position: "p2" });
  });

  it("관리를 켜면 조회도 켜지고, 확인 창을 거쳐 저장한다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/org/permissions?position=p1");
    const section = await screen.findByRole("region", { name: "운영 매니저 권한" });
    const user = userEvent.setup();

    await user.click(within(section).getByRole("checkbox", { name: "부서·팀 관리" }));
    expect(within(section).getByRole("checkbox", { name: "부서·팀 조회" })).toBeChecked();
    expect(within(section).getByText("저장하지 않은 변경 2개")).toBeInTheDocument();
    // 조회를 끄면 그 조회가 필요한 동기화도 꺼진다
    await user.click(within(section).getByRole("checkbox", { name: "수강생 명단 동기화" }));
    await user.click(within(section).getByRole("checkbox", { name: "수강생 명단 조회" }));
    expect(within(section).getByRole("checkbox", { name: "수강생 명단 동기화" })).not.toBeChecked();

    await user.click(within(section).getByRole("button", { name: "저장" }));
    const dialog = await screen.findByRole("dialog", { name: "운영 매니저 직위 권한 저장" });
    expect(within(dialog).getByRole("list", { name: "바뀐 권한" })).toHaveTextContent("부서·팀 · 조회");
    await user.click(within(dialog).getByRole("button", { name: "저장" }));
    await waitFor(() =>
      expect(calls).toEqual([{ id: "p1", body: { permissions: ["org.department.read", "org.department.manage"] } }]),
    );
    expect(await within(section).findByText("변경 사항 없음")).toBeInTheDocument();
  });

  it("변경 취소와 저장 오류", async () => {
    mockApi({ fail: true });
    await renderRoute("/admin/org/permissions");
    const section = await screen.findByRole("region", { name: "운영 매니저 권한" });
    const user = userEvent.setup();
    await user.click(within(section).getByRole("checkbox", { name: "채팅 조회" }));
    await user.click(within(section).getByRole("button", { name: "변경 취소" }));
    expect(within(section).getByRole("checkbox", { name: "채팅 조회" })).not.toBeChecked();

    await user.click(within(section).getByRole("checkbox", { name: "채팅 조회" }));
    await user.click(within(section).getByRole("button", { name: "저장" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "저장" }));
    expect(await screen.findByText("관리·동작 권한은 조회와 함께 켜야 해요.")).toBeInTheDocument();
  });

  it("저장하지 않고 다른 직위를 고르면 확인한다", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/org/permissions?position=p1");
    const section = await screen.findByRole("region", { name: "운영 매니저 권한" });
    const user = userEvent.setup();
    await user.click(within(section).getByRole("checkbox", { name: "채팅 조회" }));
    const nav = screen.getByRole("navigation", { name: "직위" });

    await user.click(within(nav).getByRole("button", { name: /팀리드/ }));
    const dialog = await screen.findByRole("dialog", { name: "저장하지 않은 변경이 있어요" });
    await user.click(within(dialog).getByRole("button", { name: "계속 고치기" }));
    expect(router.state.location.search).toEqual({ position: "p1" });
    expect(within(section).getByRole("checkbox", { name: "채팅 조회" })).toBeChecked();

    await user.click(within(nav).getByRole("button", { name: /팀리드/ }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "버리고 이동" }));
    expect(await screen.findByRole("region", { name: "팀리드 권한" })).toBeInTheDocument();
  });

  it("조회 권한만 있으면 바꿀 수 없다", async () => {
    mockApi({ codes: ["access.role.read"] });
    await renderRoute("/admin/org/permissions");
    const section = await screen.findByRole("region", { name: "운영 매니저 권한" });
    expect(within(section).getByRole("checkbox", { name: "수강생 명단 조회" })).toBeDisabled();
    expect(within(section).queryByText("변경 사항 없음")).not.toBeInTheDocument();
    expect(within(section).getByText(/볼 수만 있어요/)).toBeInTheDocument();
  });

  it("레일에 조직 모듈과 권한 메뉴가 보인다", async () => {
    mockApi();
    await renderRoute("/admin/org/permissions");
    await screen.findByRole("region", { name: "운영 매니저 권한" });
    const modules = screen.getByRole("navigation", { name: "모듈" });
    expect(within(modules).getByRole("link", { name: "조직" })).toHaveAttribute("aria-current");
    expect(
      within(screen.getByRole("navigation", { name: "메뉴" })).getByRole("link", { name: "권한" }),
    ).toHaveAttribute("aria-current", "page");
  });
});
