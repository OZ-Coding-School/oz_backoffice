import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffOptions } from "@/features/auth/staff-api";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { AdminRegistration } from "./api";
import { openCohorts, withAllCohorts } from "./api";

const ADMIN = makeMe({
  name: "김관리",
  email: "boss@nextrunners.co.kr",
  account_type: "STAFF",
  roles: [{ role: "SUPER_ADMIN", scope_type: "GLOBAL", scope_id: null, expires_at: null }],
});

function option(id: string, bootcamp: string, n: number): StaffOptions["cohorts"][number] {
  return {
    id,
    bootcamp_id: bootcamp,
    cohort_number: n,
    status: "ONGOING",
    start_date: "2026-11-01",
    end_date: "2027-04-30",
  };
}

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
  staff_roles: ["MANAGER", "ASSISTANT"],
  bootcamps: [
    { id: "b1", name: "백엔드 부트캠프", code: "BE", team_id: "t1" },
    { id: "b2", name: "디자인 부트캠프", code: "DE", team_id: "t2" },
  ],
  cohorts: [option("c12", "b1", 12)],
};

const ACCESS: StaffAccess = {
  permissions: [
    { code: "staff.registration.read", is_global: true, bootcamp_ids: [], cohort_ids: [] },
    { code: "staff.registration.manage", is_global: true, bootcamp_ids: [], cohort_ids: [] },
  ],
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
    {
      id: "c11",
      bootcamp_id: "b1",
      bootcamp_name: "백엔드 부트캠프",
      cohort_number: 11,
      start_date: "2026-05-01",
      end_date: "2026-10-31",
      status: "ENDED",
    },
    {
      id: "d5",
      bootcamp_id: "b2",
      bootcamp_name: "디자인 부트캠프",
      cohort_number: 5,
      start_date: "2026-12-01",
      end_date: "2027-05-31",
      status: "PLANNED",
    },
  ],
};

function registration(overrides: Partial<AdminRegistration> = {}): AdminRegistration {
  return {
    id: "r1",
    status: "PENDING",
    department_id: "d1",
    team_id: "t1",
    position_id: "p1",
    employment_type: "REGULAR",
    assignments: [{ role: "MANAGER", bootcamp_id: "b1", cohort_id: null }],
    reviewed_at: null,
    reject_reason: null,
    created_at: "2026-11-18T01:00:00Z",
    applicant: { id: "u1", email: "manager@nextrunners.co.kr", name: "김운영", approval_status: "PENDING" },
    ...overrides,
  };
}

const ASSISTANT = registration({
  id: "r2",
  position_id: "p2",
  employment_type: "CONTRACT",
  assignments: [{ role: "ASSISTANT", bootcamp_id: null, cohort_id: "c11" }],
  applicant: { id: "u2", email: "assistant@nextrunners.co.kr", name: "이조교", approval_status: "PENDING" },
});

function mockRegistrations({ pending = [registration(), ASSISTANT], rejected = [] as AdminRegistration[] } = {}) {
  const calls = { approve: [] as unknown[], reject: [] as unknown[] };
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(ACCESS)),
    http.get(apiUrl("/api/v1/me/staff-registration/options"), () => HttpResponse.json(OPTIONS)),
    http.get(apiUrl("/api/v1/admin/staff-registrations"), ({ request }) => {
      const status = new URL(request.url).searchParams.get("status");
      const items = status === "REJECTED" ? rejected : status === "PENDING" ? pending : [];
      return HttpResponse.json({ items, total: items.length, limit: 20, offset: 0 });
    }),
    http.post(apiUrl("/api/v1/admin/staff-registrations/{registration_id}/approve"), async ({ request, params }) => {
      calls.approve.push({ id: params.registration_id, ...((await request.json()) as object) });
      return HttpResponse.json(registration({ status: "APPROVED" }));
    }),
    http.post(apiUrl("/api/v1/admin/staff-registrations/{registration_id}/reject"), async ({ request }) => {
      calls.reject.push(await request.json());
      return HttpResponse.json(registration({ status: "REJECTED" }));
    }),
  );
  return calls;
}

describe("운영진 승인 선택지 (F61)", () => {
  it("이름표에는 담당 기수를 더하고, 넓게 볼 때는 진행 예정·진행 중 기수만", () => {
    expect(withAllCohorts(OPTIONS, ACCESS.cohorts).cohorts.map((c) => c.id)).toEqual(["c12", "c11", "d5"]);
    expect(openCohorts(ACCESS.cohorts).map((c) => c.id)).toEqual(["c12", "d5"]);
  });
});

describe("운영진 승인 (FE-15b)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("메뉴·탭·표: 부서·팀·직위·담당 이름을 보여 준다", async () => {
    mockRegistrations();
    await renderRoute("/admin/members/staff-registrations");
    expect(await screen.findByRole("heading", { name: "운영진 승인", level: 1 })).toBeInTheDocument();
    const menu = screen.getByRole("navigation", { name: "메뉴" });
    expect(await within(menu).findByRole("link", { name: /운영진 승인\s*대기\s*2/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(menu).queryByRole("link", { name: /가입 승인/ })).not.toBeInTheDocument(); // 회원 가입 승인 권한 없음
    const tabs = screen.getByRole("navigation", { name: "처리 상태" });
    expect(await within(tabs).findByRole("link", { name: "대기 2" })).toHaveAttribute("aria-current", "page");
    const manager = await screen.findByRole("row", { name: /김운영/ });
    expect(manager).toHaveTextContent("교육운영본부 · 교육 1팀");
    expect(manager).toHaveTextContent("운영 매니저");
    expect(manager).toHaveTextContent("정규직");
    expect(manager).toHaveTextContent("백엔드 부트캠프");
    // 이미 끝난 기수도 이름이 보인다 (담당 기수로 보충)
    expect(screen.getByRole("row", { name: /이조교/ })).toHaveTextContent("백엔드 부트캠프 11기");
  });

  it("검토: 고친 값으로 승인한다 — 다른 팀 과정은 스위치를 켜야 보인다", async () => {
    const calls = mockRegistrations();
    await renderRoute("/admin/members/staff-registrations");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "김운영 검토" }));
    const dialog = await screen.findByRole("dialog", { name: "운영진 승인 · 김운영" });
    expect(within(dialog).getByRole("list", { name: "추가한 담당 과정" })).toHaveTextContent("백엔드 부트캠프");
    await user.click(within(dialog).getByRole("switch", { name: "다른 팀 과정도 보기" }));
    await user.click(within(dialog).getByRole("combobox", { name: "담당 과정 추가" }));
    await user.click(await screen.findByRole("option", { name: "디자인 부트캠프" }));
    await user.click(within(dialog).getByRole("button", { name: "승인" }));
    await waitFor(() =>
      expect(calls.approve).toEqual([
        {
          id: "r1",
          department_id: "d1",
          team_id: "t1",
          position_id: "p1",
          employment_type: "REGULAR",
          assignments: [
            { role: "MANAGER", bootcamp_id: "b1", cohort_id: null },
            { role: "MANAGER", bootcamp_id: "b2", cohort_id: null },
          ],
        },
      ]),
    );
    expect(await screen.findByText("김운영님을 운영진으로 승인했어요")).toBeInTheDocument();
  });

  it("반려: 같은 창에서 사유를 적는다", async () => {
    const calls = mockRegistrations();
    await renderRoute("/admin/members/staff-registrations");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "김운영 검토" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "반려" }));
    const dialog = await screen.findByRole("dialog", { name: "운영진 신청 반려 · 김운영" });
    const button = within(dialog).getByRole("button", { name: "반려" });
    expect(button).toBeDisabled();
    await user.type(within(dialog).getByRole("textbox", { name: "반려 사유" }), "담당 과정 확인");
    await user.click(button);
    await waitFor(() => expect(calls.reject).toEqual([{ reason: "담당 과정 확인" }]));
  });

  it("반려 탭은 읽기만, 처리일·사유를 보여 준다", async () => {
    mockRegistrations({
      rejected: [registration({ status: "REJECTED", reviewed_at: "2026-11-19T01:00:00Z", reject_reason: "소속 확인" })],
    });
    await renderRoute("/admin/members/staff-registrations?status=rejected");
    const row = await screen.findByRole("row", { name: /김운영/ });
    expect(row).toHaveTextContent("11/19");
    expect(row).toHaveTextContent("소속 확인");
    expect(within(row).queryByRole("button")).not.toBeInTheDocument();
  });
});
