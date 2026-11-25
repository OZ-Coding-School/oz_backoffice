import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffOptions } from "@/features/auth/staff-api";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { Department, OrgImpact, Team } from "./api";
import { eul } from "./text";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: true });

const DEPARTMENTS: Department[] = [
  { id: "d1", name: "교육운영본부", description: "부트캠프 운영 전반", rules: "매주 월요일 공유", employee_count: 17 },
  { id: "d2", name: "경영지원본부", description: "인사·재무", rules: null, employee_count: 0 },
];
const TEAMS: Team[] = [
  {
    id: "t1",
    department_id: "d1",
    name: "교육 1팀",
    description: "백엔드 운영",
    bootcamp_ids: ["b1"],
    employee_count: 8,
  },
  { id: "t2", department_id: "d1", name: "교육 2팀", description: null, bootcamp_ids: ["b2"], employee_count: 7 },
];
const OPTIONS: StaffOptions = {
  departments: [],
  teams: [],
  positions: [],
  employment_types: [],
  bootcamps: [
    { id: "b1", name: "백엔드 부트캠프", code: "BE", team_id: "t1" },
    { id: "b2", name: "디자인 부트캠프", code: "DE", team_id: "t2" },
    { id: "b3", name: "데이터 분석 부트캠프", code: "DA", team_id: null },
  ],
  cohorts: [],
};
const EMPTY: OrgImpact = { employees: [], registrations: [], teams: [], bootcamps: [] };
const TEAM_IMPACT: OrgImpact = {
  employees: [
    {
      id: "e1",
      user_id: "u1",
      name: "김운영",
      email: "manager@nextrunners.co.kr",
      department_name: "교육운영본부",
      team_name: "교육 1팀",
      position_name: "운영 매니저",
    },
  ],
  registrations: [{ id: "r1", applicant_name: "정신청", applicant_email: "jung@nextrunners.co.kr", status: "PENDING" }],
  teams: [],
  bootcamps: [{ id: "b1", name: "백엔드 부트캠프" }],
};

function access(codes: string[]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [],
  };
}

function mockApi({ codes = ["org.department.read", "org.department.manage"], teamImpact = TEAM_IMPACT } = {}) {
  const calls: { method: string; path: string; body?: unknown; query?: string }[] = [];
  const record = async (request: Request) => {
    const url = new URL(request.url);
    const body = request.method === "GET" || request.method === "DELETE" ? undefined : await request.json();
    calls.push({ method: request.method, path: url.pathname.replace("/api/v1", ""), body, query: url.search });
  };
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/me/staff-registration/options"), () => HttpResponse.json(OPTIONS)),
    http.get(apiUrl("/api/v1/admin/departments"), () => HttpResponse.json(DEPARTMENTS)),
    http.get(apiUrl("/api/v1/admin/teams"), () => HttpResponse.json(TEAMS)),
    http.get(apiUrl("/api/v1/admin/teams/{team_id}/impact"), () => HttpResponse.json(teamImpact)),
    http.get(apiUrl("/api/v1/admin/departments/{department_id}/impact"), ({ params }) =>
      HttpResponse.json(
        params.department_id === "d1"
          ? { ...EMPTY, teams: [{ id: "t1", name: "교육 1팀", employee_count: 8 }], employees: TEAM_IMPACT.employees }
          : EMPTY,
      ),
    ),
    http.post(apiUrl("/api/v1/admin/departments"), async ({ request }) => {
      const body = (await request.clone().json()) as { name: string };
      await record(request);
      if (body.name === "교육운영본부")
        return HttpResponse.json(
          { error: { code: "department_name_taken", message: "같은 이름의 부서가 있습니다." } },
          { status: 409 },
        );
      return HttpResponse.json({ ...DEPARTMENTS[1], id: "d9", ...body }, { status: 201 });
    }),
    http.delete(apiUrl("/api/v1/admin/departments/{department_id}"), async ({ request }) => {
      await record(request);
      return new HttpResponse(null, { status: 204 });
    }),
    http.patch(apiUrl("/api/v1/admin/teams/{team_id}"), async ({ request, params }) => {
      const body = (await request.clone().json()) as object;
      await record(request);
      const team = TEAMS.find((t) => t.id === params.team_id) ?? TEAMS[0];
      return HttpResponse.json({ ...team, ...body });
    }),
    http.put(apiUrl("/api/v1/admin/bootcamps/{bootcamp_id}/team"), async ({ request, params }) => {
      const body = (await request.clone().json()) as { team_id: string | null };
      await record(request);
      return HttpResponse.json({ bootcamp_id: String(params.bootcamp_id), team_id: body.team_id });
    }),
    http.delete(apiUrl("/api/v1/admin/teams/{team_id}"), async ({ request }) => {
      await record(request);
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return calls;
}

describe("목적격 조사", () => {
  it("받침이 있으면 을, 없으면 를", () => {
    expect(eul("교육 1팀")).toBe("교육 1팀을");
    expect(eul("교육운영본부")).toBe("교육운영본부를");
    expect(eul("QA")).toBe("QA을(를)");
  });
});

describe("조직 설정 > 부서 (FE-15g)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("목록 보기: 부서 아래 팀, 담당 과정·직원 수, 부서 접기, 메뉴", async () => {
    mockApi();
    await renderRoute("/admin/org/departments");
    const table = await screen.findByRole("table", { name: "부서" });
    expect(within(table).getByRole("row", { name: "교육운영본부" })).toHaveTextContent("팀 2개 · 과정 2개");
    expect(within(table).getByRole("row", { name: "교육 1팀" })).toHaveTextContent("백엔드 부트캠프");
    expect(within(table).getByRole("row", { name: "교육 1팀" })).toHaveTextContent("8명");
    expect(screen.getByText("부서 2개 · 팀 2개 · 직원 17명")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(table).getByRole("button", { name: "교육운영본부 팀 접기" }));
    expect(within(table).queryByRole("row", { name: "교육 1팀" })).not.toBeInTheDocument();
    const menu = screen.getByRole("navigation", { name: "메뉴" });
    expect(within(menu).getByRole("link", { name: "부서" })).toHaveAttribute("aria-current", "page");
  });

  it("트리 보기: 조직도 상자를 누르면 패널이 열린다", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/org/departments?view=tree");
    const chart = await screen.findByRole("region", { name: "조직도" });
    expect(within(chart).getByText("넥스트러너스")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(chart).getByRole("link", { name: "교육 2팀" }));
    const sheet = await screen.findByRole("dialog", { name: "교육 2팀" });
    expect(router.state.location.search).toEqual({ view: "tree", team: "t2" });
    expect(within(sheet).getByRole("list", { name: "담당 과정" })).toHaveTextContent("디자인 부트캠프");
  });

  it("팀 수정: 담당 과정을 빼고 다른 과정을 더해 저장한다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/org/departments?team=t1");
    const sheet = await screen.findByRole("dialog", { name: "교육 1팀" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    const name = within(sheet).getByRole("textbox", { name: "이름" });
    await user.clear(name);
    await user.type(name, "백엔드팀");
    await user.click(within(sheet).getByRole("button", { name: "백엔드 부트캠프 빼기" }));
    await user.click(within(sheet).getByRole("combobox", { name: "담당 과정 추가" }));
    // 다른 팀 담당 과정은 옮겨 온다고 알려 준다
    expect(await screen.findByRole("option", { name: /디자인 부트캠프 \(지금 교육 2팀/ })).toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: "데이터 분석 부트캠프" }));
    await user.click(within(sheet).getByRole("button", { name: "저장" }));
    await waitFor(() =>
      expect(calls).toEqual([
        {
          method: "PATCH",
          path: "/admin/teams/t1",
          body: { name: "백엔드팀", department_id: "d1", description: "백엔드 운영" },
          query: "",
        },
        { method: "PUT", path: "/admin/bootcamps/b1/team", body: { team_id: null }, query: "" },
        { method: "PUT", path: "/admin/bootcamps/b3/team", body: { team_id: "t1" }, query: "" },
      ]),
    );
    expect(await screen.findByText("백엔드팀 팀을 저장했어요")).toBeInTheDocument();
  });

  it("팀의 부서를 바꾸면 함께 옮겨 갈 직원·신청을 보여 준다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/org/departments?team=t1");
    const sheet = await screen.findByRole("dialog", { name: "교육 1팀" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    await user.click(within(sheet).getByRole("combobox", { name: "부서" }));
    await user.click(await screen.findByRole("option", { name: "경영지원본부" }));
    await user.click(within(sheet).getByRole("button", { name: "저장" }));
    const dialog = await screen.findByRole("dialog", { name: "교육 1팀을 경영지원본부로 옮길까요?" });
    // 종류별 상자는 처음에 접혀 있다 (F69)
    const employees = await within(dialog).findByRole("button", { name: /직원\s*1명/ });
    expect(employees).toHaveAttribute("aria-expanded", "false");
    await user.click(employees);
    expect(within(dialog).getByRole("list", { name: "직원" })).toHaveTextContent("김운영");
    expect(within(dialog).queryByRole("button", { name: /담당 과정/ })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "옮기고 저장" }));
    await waitFor(() => expect(calls[0]?.body).toMatchObject({ department_id: "d2" }));
  });

  it("팀 삭제: 대상이 있으면 옮길 팀을 골라야 지운다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/org/departments?team=t1");
    const sheet = await screen.findByRole("dialog", { name: "교육 1팀" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "삭제" }));
    const dialog = await screen.findByRole("dialog", { name: "교육 1팀을 삭제할까요?" });
    await within(dialog).findByRole("button", { name: /운영진 가입 신청/ });
    const remove = within(dialog).getByRole("button", { name: "삭제" });
    expect(remove).toBeDisabled();
    await user.click(within(dialog).getByRole("combobox", { name: "옮길 팀" }));
    await user.click(await screen.findByRole("option", { name: "교육운영본부 · 교육 2팀" }));
    await user.click(remove);
    await waitFor(() =>
      expect(calls).toEqual([{ method: "DELETE", path: "/admin/teams/t1", query: "?move_to_team_id=t2" }]),
    );
  });

  it("부서 삭제: 남은 팀·직원이 있으면 목록과 [닫기]만", async () => {
    mockApi();
    await renderRoute("/admin/org/departments?department=d1");
    const sheet = await screen.findByRole("dialog", { name: "교육운영본부" });
    expect(within(sheet).getByRole("region", { name: "규칙" })).toHaveTextContent("매주 월요일 공유");
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "삭제" }));
    const dialog = await screen.findByRole("dialog", { name: "교육운영본부를 지울 수 없어요" });
    await user.click(await within(dialog).findByRole("button", { name: /팀\s*1개/ }));
    expect(within(dialog).getByRole("list", { name: "팀" })).toHaveTextContent("교육 1팀");
    expect(within(dialog).queryByRole("button", { name: "삭제" })).not.toBeInTheDocument();
    expect(within(dialog).getByText("닫기", { selector: "button" })).toBeInTheDocument();
  });

  it("부서 추가: 같은 이름이면 이름 칸에 알린다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/org/departments");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "부서 추가" }));
    const sheet = await screen.findByRole("dialog", { name: "새 부서" });
    await user.type(within(sheet).getByRole("textbox", { name: "이름" }), "교육운영본부");
    await user.type(within(sheet).getByRole("textbox", { name: "설명" }), "운영");
    await user.click(within(sheet).getByRole("button", { name: "저장" }));
    expect(await within(sheet).findByText("같은 이름의 부서가 있어요.")).toBeInTheDocument();
    expect(calls[0]).toMatchObject({
      method: "POST",
      body: { name: "교육운영본부", description: "운영", rules: null },
    });
  });

  it("조회 권한만 있으면 추가·수정 버튼이 없다", async () => {
    mockApi({ codes: ["org.department.read"] });
    await renderRoute("/admin/org/departments?department=d2");
    const sheet = await screen.findByRole("dialog", { name: "경영지원본부" });
    expect(within(sheet).queryByRole("button", { name: "수정" })).not.toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "삭제" })).not.toBeInTheDocument();
    expect(within(sheet).getByText("정한 규칙이 없어요.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "부서 추가", hidden: true })).not.toBeInTheDocument();
  });
});
