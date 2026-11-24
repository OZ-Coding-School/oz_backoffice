import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffOptions } from "@/features/auth/staff-api";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { Employee, StaffMember } from "./api";
import { assignmentsSummary } from "./api";

const ADMIN = makeMe({
  name: "김관리",
  email: "boss@nextrunners.co.kr",
  account_type: "STAFF",
  is_super_admin: true,
});

const OPTIONS: StaffOptions = {
  departments: [{ id: "d1", name: "교육운영본부" }],
  teams: [
    { id: "t1", department_id: "d1", name: "교육 1팀" },
    { id: "t2", department_id: "d1", name: "교육 2팀" },
  ],
  positions: [
    { id: "p1", name: "운영 매니저", assignment_scope: "COURSE" },
    { id: "p2", name: "조교", assignment_scope: "COHORT" },
  ],
  employment_types: ["REGULAR", "CONTRACT"],
  bootcamps: [{ id: "b1", name: "백엔드 부트캠프", code: "BE", team_id: "t1" }],
  cohorts: [],
};

function access(codes: string[]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [
      {
        id: "c12",
        bootcamp_id: "b1",
        bootcamp_name: "백엔드 부트캠프",
        cohort_number: 12,
        start_date: "2026-11-01",
        end_date: "2027-04-30",
        status: "ONGOING",
      },
    ],
  };
}

function employee(overrides: Partial<Employee> = {}): Employee {
  return {
    id: "e1",
    user: { id: "u1", email: "manager@nextrunners.co.kr", name: "김운영" },
    department_id: "d1",
    team_id: "t1",
    position_id: "p1",
    employment_type: "REGULAR",
    assignments: [
      {
        staff_id: "s1",
        bootcamp_id: "b1",
        cohort_id: null,
        bootcamp_name: "백엔드 부트캠프",
        cohort_number: null,
      },
      {
        staff_id: "s2",
        bootcamp_id: null,
        cohort_id: "c12",
        bootcamp_name: "백엔드 부트캠프",
        cohort_number: 12,
      },
    ],
    ...overrides,
  };
}

const LEE = employee({
  id: "e2",
  user: { id: "u2", email: "lee@nextrunners.co.kr", name: "이조교" },
  position_id: "p2",
  employment_type: "CONTRACT",
  assignments: [],
});

const MEMBER: StaffMember = {
  id: "cs1",
  employee_id: "e2",
  user: { id: "u2", email: "lee@nextrunners.co.kr", name: "이조교" },
  created_at: "2026-11-18T01:00:00Z",
};

function mockStaff(
  codes = ["org.employee.read", "org.employee.manage", "staff.assignment.read", "staff.assignment.manage"],
) {
  const calls = { q: [] as (string | null)[], patch: [] as unknown[], add: [] as unknown[], remove: [] as string[] };
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/me/staff-registration/options"), () => HttpResponse.json(OPTIONS)),
    http.get(apiUrl("/api/v1/admin/employees"), ({ request }) => {
      const q = new URL(request.url).searchParams.get("q");
      calls.q.push(q);
      const items = q ? [employee(), LEE].filter((e) => e.user?.name.includes(q)) : [employee(), LEE];
      return HttpResponse.json({ items, total: items.length, limit: 20, offset: 0 });
    }),
    http.patch(apiUrl("/api/v1/admin/employees/{employee_id}"), async ({ request }) => {
      calls.patch.push(await request.json());
      return HttpResponse.json(employee());
    }),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/staffs"), () => HttpResponse.json([MEMBER])),
    http.get(apiUrl("/api/v1/admin/bootcamps/{bootcamp_id}/staffs"), () => HttpResponse.json([])),
    http.post(apiUrl("/api/v1/admin/cohorts/{cohort_id}/staffs"), async ({ request }) => {
      calls.add.push(await request.json());
      return HttpResponse.json(MEMBER, { status: 201 });
    }),
    http.delete(apiUrl("/api/v1/admin/cohorts/{cohort_id}/staffs/{staff_id}"), ({ params }) => {
      calls.remove.push(String(params.staff_id));
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return calls;
}

describe("담당 요약 (A83)", () => {
  it("첫 대상과 외 N, 없으면 없음", () => {
    expect(assignmentsSummary(employee().assignments ?? [])).toBe("백엔드 부트캠프 외 1");
    expect(assignmentsSummary([])).toBe("없음");
  });
});

describe("직원·담당자 (FE-15c)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("직원 탭: 표·검색, 소속 수정", async () => {
    const calls = mockStaff();
    const { router } = await renderRoute("/admin/members/staff");
    expect(await screen.findByRole("heading", { name: "직원·담당자", level: 1 })).toBeInTheDocument();
    const row = await screen.findByRole("row", { name: /김운영/ });
    expect(row).toHaveTextContent("교육운영본부 · 교육 1팀");
    expect(row).toHaveTextContent("백엔드 부트캠프 외 1");
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox", { name: "직원 검색" }), "이조");
    await waitFor(() => expect(router.state.location.search).toEqual({ q: "이조" }));
    await waitFor(() => expect(screen.queryByRole("row", { name: /김운영/ })).not.toBeInTheDocument());
    expect(calls.q).toContain("이조");

    await user.click(screen.getByRole("button", { name: "이조교 수정" }));
    const dialog = await screen.findByRole("dialog", { name: "소속 수정 · 이조교" });
    expect(within(dialog).queryByText("담당 기수")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("combobox", { name: "팀" }));
    await user.click(await screen.findByRole("option", { name: "교육 2팀" }));
    await user.click(within(dialog).getByRole("button", { name: "저장" }));
    await waitFor(() =>
      expect(calls.patch).toEqual([
        { department_id: "d1", team_id: "t2", position_id: "p2", employment_type: "CONTRACT" },
      ]),
    );
  });

  it("담당자 탭: 과정·기수를 고르면 목록, 추가·해제", async () => {
    const calls = mockStaff();
    await renderRoute("/admin/members/staff?tab=staff&bootcamp=b1&cohort=c12");
    const table = await screen.findByRole("table", { name: "백엔드 부트캠프 12기 담당자" });
    expect(within(table).getByRole("row", { name: /이조교/ })).toHaveTextContent("조교");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "담당자 추가" }));
    const dialog = await screen.findByRole("dialog", { name: "담당자 추가" });
    expect(await within(dialog).findByRole("radio", { name: "이조교" })).toBeDisabled(); // 담당 중
    await user.click(within(dialog).getByRole("radio", { name: "김운영" }));
    await user.click(within(dialog).getByRole("button", { name: "추가" }));
    await waitFor(() => expect(calls.add).toEqual([{ employee_id: "e1" }]));

    await user.click(await screen.findByRole("button", { name: "이조교 해제" }));
    await user.click(await screen.findByRole("button", { name: "빼기" }));
    await waitFor(() => expect(calls.remove).toEqual(["cs1"]));
  });

  it("팀리드(직원 조회)는 직원 탭을 읽기만, 직원 권한만 있으면 담당자 탭이 없다", async () => {
    mockStaff(["org.employee.read", "staff.assignment.read", "staff.assignment.manage"]);
    const { unmount } = await renderRoute("/admin/members/staff");
    await screen.findByRole("row", { name: /김운영/ });
    expect(screen.queryByRole("button", { name: "김운영 수정" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "담당자" })).toBeInTheDocument();
    unmount();

    mockStaff(["org.employee.read", "org.employee.manage"]);
    await renderRoute("/admin/members/staff?tab=staff");
    await screen.findByRole("row", { name: /김운영/ });
    expect(screen.queryByRole("link", { name: "담당자" })).not.toBeInTheDocument();
  });

  it("담당자 조회만 있으면 담당자 탭에서 추가·해제가 없다 (A86)", async () => {
    mockStaff(["staff.assignment.read"]);
    await renderRoute("/admin/members/staff?tab=staff&bootcamp=b1&cohort=c12");
    await screen.findByRole("table", { name: /담당자/ });
    expect(screen.queryByRole("button", { name: "담당자 추가" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /해제/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "직원" })).not.toBeInTheDocument();
  });
});
