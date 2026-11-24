import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { StaffAccess, StaffCohort } from "./api";
import { hasPermission } from "./api";
import { roleLines } from "./labels";
import { currentStaffNav, staffModules } from "./nav";

const C12: StaffCohort = {
  id: "c12",
  bootcamp_id: "b1",
  bootcamp_name: "백엔드 부트캠프",
  cohort_number: 12,
  start_date: "2026-11-01",
  end_date: "2027-04-30",
  status: "ONGOING",
};

const MANAGER_ACCESS: StaffAccess = {
  permissions: [{ code: "user.approve", is_global: false, bootcamp_ids: [], cohort_ids: ["c12"] }],
  cohorts: [C12],
};

const STAFF = makeMe({
  name: "김운영",
  email: "staff@nextrunners.co.kr",
  account_type: "STAFF",
  roles: [
    { role: "SUPER_ADMIN", scope_type: "GLOBAL", scope_id: null, expires_at: null },
    { role: "COHORT_MANAGER", scope_type: "COHORT", scope_id: "c12", expires_at: null },
    { role: "COHORT_ASSISTANT", scope_type: "BOOTCAMP", scope_id: "b1", expires_at: null },
    { role: "COHORT_ASSISTANT", scope_type: "COHORT", scope_id: "unknown", expires_at: null },
  ],
});

describe("운영진 메뉴·역할 (F17·F58)", () => {
  it("권한으로 메뉴를 거르고 메뉴가 없는 모듈은 뺀다", () => {
    expect(hasPermission(MANAGER_ACCESS, "user.approve")).toBe(true);
    expect(hasPermission(MANAGER_ACCESS, "org.manage")).toBe(false);
    const modules = staffModules({ permissions: [] });
    expect(modules.map((m) => m.key)).toEqual(["home"]);
    expect(currentStaffNav(modules, "/admin")?.item.label).toBe("홈");
    expect(currentStaffNav(modules, "/unknown")).toBeUndefined();
  });

  it("역할 줄: 전체는 이름만, 과정·기수는 그 이름을 앞에, 모르는 범위는 이름만", () => {
    expect(roleLines(STAFF.roles, [C12])).toEqual([
      "최고 관리자",
      "백엔드 부트캠프 12기 운영 매니저",
      "백엔드 부트캠프 조교",
      "조교",
    ]);
  });
});

describe("운영진 틀 (FE-14a)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(STAFF);
  });

  it("모듈 레일·모듈 메뉴·위치를 보여 주고, 사용자 메뉴에 역할을 보여 준다", async () => {
    server.use(http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(MANAGER_ACCESS)));
    await renderRoute("/admin");
    expect(await screen.findByRole("heading", { name: "안녕하세요, 김운영님" })).toBeInTheDocument();
    const modules = screen.getByRole("navigation", { name: "모듈" });
    expect(within(modules).getByRole("link", { name: "홈" })).toHaveAttribute("aria-current");
    const menu = screen.getByRole("navigation", { name: "메뉴" });
    expect(within(menu).getByRole("link", { name: "홈" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("navigation", { name: "위치" })).toHaveTextContent("홈");
    expect(screen.getByText("처리할 일 요약이 곧 여기에 모여요")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "사용자 메뉴" }));
    const popup = await screen.findByRole("menu");
    expect(popup).toHaveTextContent("김운영");
    expect(popup).toHaveTextContent("백엔드 부트캠프 12기 운영 매니저");
    expect(within(popup).getByRole("menuitem", { name: "로그아웃" })).toBeInTheDocument();
  });

  it("권한이 하나도 없으면 안내한다", async () => {
    await renderRoute("/admin");
    expect(await screen.findByRole("heading", { name: "아직 받은 권한이 없어요" })).toBeInTheDocument();
  });

  it("로그아웃하면 운영진 로그인으로 간다", async () => {
    const { router } = await renderRoute("/admin");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "사용자 메뉴" }));
    await user.click(await screen.findByRole("menuitem", { name: "로그아웃" }));
    await vi.waitFor(() => expect(router.state.location.pathname).toMatch(/login/));
  });
});
