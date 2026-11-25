import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffOptions } from "@/features/auth/staff-api";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { Employee } from "./api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: true });

const OPTIONS: StaffOptions = {
  departments: [
    { id: "d1", name: "교육운영본부" },
    { id: "d2", name: "경영지원본부" },
  ],
  teams: [{ id: "t1", department_id: "d1", name: "교육 1팀" }],
  positions: [
    { id: "p1", name: "운영 매니저", assignment_scope: "COURSE" },
    { id: "p2", name: "조교", assignment_scope: "COHORT" },
  ],
  employment_types: ["REGULAR", "CONTRACT"],
  bootcamps: [
    { id: "b1", name: "백엔드 부트캠프", code: "BE", team_id: "t1" },
    { id: "b2", name: "디자인 부트캠프", code: "DE", team_id: "t1" },
  ],
  cohorts: [],
};

function employee(overrides: Partial<Employee> = {}): Employee {
  return {
    id: "e1",
    user: { id: "u1", email: "manager@nextrunners.co.kr", name: "김운영" },
    department_id: "d1",
    team_id: "t1",
    position_id: "p1",
    employment_type: "REGULAR",
    assignments: [
      { staff_id: "s1", bootcamp_id: "b1", cohort_id: null, bootcamp_name: "백엔드 부트캠프", cohort_number: null },
    ],
    is_super_admin: false,
    data_scope: "ASSIGNED",
    ...overrides,
  };
}

const LEE = employee({
  id: "e2",
  user: { id: "u2", email: "lee@nextrunners.co.kr", name: "이조교" },
  position_id: "p2",
  assignments: [],
});
const PARK = employee({
  id: "e3",
  user: { id: "u3", email: "park@nextrunners.co.kr", name: "박인사" },
  department_id: "d2",
  team_id: null,
  assignments: [],
  is_super_admin: true,
  data_scope: "ALL",
});

function access(codes: string[], superAdmin = false): StaffAccess {
  return {
    is_super_admin: superAdmin,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [],
  };
}

const MANAGE = ["org.employee.read", "org.employee.manage", "staff.assignment.read", "staff.assignment.manage"];

function mockApi({ codes = MANAGE, superAdmin = true, fail = false } = {}) {
  const calls: unknown[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes, superAdmin))),
    http.get(apiUrl("/api/v1/me/staff-registration/options"), () => HttpResponse.json(OPTIONS)),
    http.get(apiUrl("/api/v1/admin/employees"), () => HttpResponse.json([employee(), LEE, PARK])),
    http.patch(apiUrl("/api/v1/admin/employees/{employee_id}"), async ({ request }) => {
      const body = (await request.json()) as Partial<Employee>;
      calls.push(body);
      if (fail) {
        return HttpResponse.json(
          { error: { code: "last_super_admin", message: "마지막 최고 관리자는 끌 수 없습니다." } },
          { status: 409 },
        );
      }
      return HttpResponse.json(employee({ ...body } as Partial<Employee>));
    }),
  );
  return calls;
}

describe("조직 설정 > 직원 (FE-15f)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("부서 › 팀으로 묶고, 검색하고, 부서를 접는다", async () => {
    mockApi();
    await renderRoute("/admin/org/employees");
    const table = await screen.findByRole("table", { name: "직원" });
    expect(within(table).getByRole("rowgroup", { name: "교육운영본부 교육 1팀" })).toHaveTextContent("김운영");
    expect(within(table).getByRole("rowgroup", { name: "경영지원본부 팀 없음" })).toHaveTextContent("박인사");
    expect(within(table).getByRole("row", { name: "김운영" })).toHaveTextContent("백엔드 부트캠프");
    expect(within(table).getByRole("row", { name: "박인사" })).toHaveTextContent("최고 관리자");
    expect(screen.getByText("직원 3명")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(within(table).getByRole("button", { name: /교육운영본부/ }));
    expect(within(table).queryByRole("row", { name: "김운영" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "모두 펼치기" }));
    expect(within(table).getByRole("row", { name: "김운영" })).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "직원 검색" }), "park@");
    expect(within(table).queryByRole("row", { name: "김운영" })).not.toBeInTheDocument();
    expect(screen.getByText("직원 1명")).toBeInTheDocument();
    await user.clear(screen.getByRole("textbox", { name: "직원 검색" }));
    await user.type(screen.getByRole("textbox", { name: "직원 검색" }), "없는 사람");
    expect(screen.getByRole("heading", { name: "찾는 직원이 없어요" })).toBeInTheDocument();
  });

  it("행을 누르면 패널이 열리고 섹션별로 보여 준다", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/org/employees");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: "김운영" }));
    const sheet = await screen.findByRole("dialog", { name: "김운영" });
    expect(router.state.location.search).toEqual({ employee: "e1" });
    expect(within(sheet).getByRole("region", { name: "소속" })).toHaveTextContent("교육운영본부");
    expect(within(sheet).getByRole("region", { name: "직위·권한" })).toHaveTextContent("담당 과정·기수만");
    expect(within(sheet).getByRole("list", { name: "담당 과정" })).toHaveTextContent("백엔드 부트캠프");
    expect(within(sheet).getByRole("region", { name: "직위·권한" })).toHaveTextContent("최고 관리자지정 안 됨");
    // 설명은 ? 아이콘을 누르면 보인다 (F68)
    await user.click(within(sheet).getByRole("button", { name: "최고 관리자 설명" }));
    expect(await screen.findByText(/직위와 상관없이 모든 권한과 모든 데이터/)).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await user.click(within(sheet).getByRole("button", { name: "닫기" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(router.state.location.search).toEqual({});
  });

  it("담당이 없는 직위는 담당 섹션이 없고, 기수 담당은 '담당 기수'", async () => {
    mockApi();
    await renderRoute("/admin/org/employees?employee=e2");
    const sheet = await screen.findByRole("dialog", { name: "이조교" });
    expect(within(sheet).getByRole("region", { name: "담당 기수" })).toHaveTextContent("담당이 없어요");
  });

  it("같은 패널에서 고쳐 저장한다 (최고 관리자 스위치 포함)", async () => {
    const calls = mockApi();
    await renderRoute("/admin/org/employees?employee=e1");
    const sheet = await screen.findByRole("dialog", { name: "김운영" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    const form = within(sheet).getByRole("form", { name: "직원 수정" });

    await user.click(within(form).getByRole("combobox", { name: "고용 형태" }));
    await user.click(await screen.findByRole("option", { name: "계약직" }));
    await user.click(within(form).getByRole("button", { name: "백엔드 부트캠프 빼기" }));
    await user.click(within(form).getByRole("combobox", { name: "담당 과정 추가" }));
    await user.click(await screen.findByRole("option", { name: "디자인 부트캠프" }));
    await user.click(within(form).getByRole("switch", { name: "최고 관리자" }));
    await user.click(within(form).getByRole("button", { name: "저장" }));

    await waitFor(() =>
      expect(calls).toEqual([
        { employment_type: "CONTRACT", bootcamp_ids: ["b2"], cohort_ids: [], is_super_admin: true },
      ]),
    );
    expect(await screen.findByText("김운영님 정보를 저장했어요")).toBeInTheDocument();
    expect(within(sheet).queryByRole("form")).not.toBeInTheDocument();
  });

  it("저장 오류는 패널 안에 보여 준다", async () => {
    mockApi({ fail: true });
    await renderRoute("/admin/org/employees?employee=e1");
    const sheet = await screen.findByRole("dialog", { name: "김운영" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    await user.click(within(sheet).getByRole("switch", { name: "최고 관리자" }));
    await user.click(within(sheet).getByRole("button", { name: "저장" }));
    expect(await within(sheet).findByText("마지막 최고 관리자는 끌 수 없습니다.")).toBeInTheDocument();
  });

  it("저장하지 않고 닫으면 확인한다", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/org/employees?employee=e1");
    const sheet = await screen.findByRole("dialog", { name: "김운영" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    await user.click(within(sheet).getByRole("switch", { name: "최고 관리자" }));
    await user.click(within(sheet).getByRole("button", { name: "닫기" }));
    const confirm = await screen.findByRole("dialog", { name: "저장하지 않은 변경이 있어요" });
    await user.click(within(confirm).getByRole("button", { name: "계속 고치기" }));
    expect(router.state.location.search).toEqual({ employee: "e1" });
    await user.click(within(sheet).getByRole("button", { name: "닫기" }));
    await user.click(
      within(await screen.findByRole("dialog", { name: "저장하지 않은 변경이 있어요" })).getByRole("button", {
        name: "버리고 닫기",
      }),
    );
    await waitFor(() => expect(router.state.location.search).toEqual({}));
  });

  it("담당 권한만 있으면 소속은 글자로, 최고 관리자 스위치는 없다", async () => {
    mockApi({ codes: ["org.employee.read", "staff.assignment.read", "staff.assignment.manage"], superAdmin: false });
    await renderRoute("/admin/org/employees?employee=e1");
    const sheet = await screen.findByRole("dialog", { name: "김운영" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    expect(within(sheet).queryByRole("combobox", { name: "부서" })).not.toBeInTheDocument();
    expect(within(sheet).getByRole("region", { name: "소속" })).toHaveTextContent("교육운영본부");
    expect(within(sheet).getByRole("combobox", { name: "담당 과정 추가" })).toBeInTheDocument();
    expect(within(sheet).queryByRole("switch")).not.toBeInTheDocument();
  });

  it("조회 권한만 있으면 [수정]이 없다. 메뉴는 조직 설정 > 직원", async () => {
    mockApi({ codes: ["org.employee.read"], superAdmin: false });
    await renderRoute("/admin/org/employees?employee=e1");
    const sheet = await screen.findByRole("dialog", { name: "김운영" });
    expect(within(sheet).queryByRole("button", { name: "수정" })).not.toBeInTheDocument();
    const menu = screen.getByRole("navigation", { name: "메뉴", hidden: true });
    expect(within(menu).getByRole("link", { name: "직원", hidden: true })).toHaveAttribute("aria-current", "page");
    expect(within(menu).queryByRole("link", { name: "권한", hidden: true })).not.toBeInTheDocument();
  });
});
