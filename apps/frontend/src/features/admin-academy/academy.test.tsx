import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { Bootcamp, Cohort, CohortSummary } from "./api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });

const bootcamp = (id: string, name: string, code: string, extra: Partial<Bootcamp> = {}): Bootcamp => ({
  id,
  name,
  code,
  hrd_net_bootcamp_id: `h-${id}`,
  is_active: true,
  airtable_cohort_prefix: name.slice(0, 3),
  hrd_net_id: `AIG${id}`,
  hrd_bootcamp_name: `${name} HRD`,
  ...extra,
});
const BE = bootcamp("b1", "백엔드 부트캠프", "BE");
const CEO = bootcamp("b2", "CEO 과정", "CEO", { is_active: false });
const FE = bootcamp("b3", "프론트엔드 부트캠프", "FE");

const cohort = (id: string, n: number, status: Cohort["status"], extra: Partial<Cohort> = {}): Cohort => ({
  id,
  bootcamp_id: "b1",
  hrd_net_cohort_id: `hc-${id}`,
  cohort_number: n,
  start_date: "2026-06-02",
  end_date: "2026-11-30",
  status,
  discord_guild_id: null,
  hrd_net_id: "AIGb1",
  hrd_cohort_number: n,
  ...extra,
});
const C12 = cohort("c12", 12, "ONGOING", { discord_guild_id: "1203948576612345678" });
const C11 = cohort("c11", 11, "ENDED");
const C9 = cohort("c9", 9, "ARCHIVED");

const SUMMARY: CohortSummary = {
  students: {
    total: 34,
    linked: 28,
    by_status: { ENROLLED: 30, COMPLETED: 0, DROPPED: 2, EARLY_EMPLOYED: 1, TRANSFERRED: 1 },
  },
  mentors: [{ mentor_id: "m1", name: "이멘토", start_date: "2026-11-02" }],
  staff: [
    { employee_id: "e1", name: "박매니저", position_name: "운영 매니저", scope: "COHORT" },
    { employee_id: "e2", name: "최팀장", position_name: "팀장", scope: "COURSE" },
  ],
};

function access(codes: string[]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [],
  };
}

const ALL = [
  "academy.bootcamp.read",
  "academy.bootcamp.manage",
  "academy.cohort.read",
  "academy.cohort.manage",
  "mentoring.settings.read",
  "org.department.read",
  "org.department.manage",
];

function mockApi({ codes = ALL, settings = true } = {}) {
  const patches: { path: string; body: unknown }[] = [];
  const puts: unknown[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/admin/bootcamps"), () => HttpResponse.json([BE, CEO, FE])),
    http.get(apiUrl("/api/v1/admin/bootcamps/{bootcamp_id}/cohorts"), ({ params }) =>
      HttpResponse.json(params.bootcamp_id === "b1" ? [C11, C9, C12] : []),
    ),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}"), ({ params }) =>
      HttpResponse.json([C12, C11, C9].find((c) => c.id === params.cohort_id)),
    ),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/summary"), () => HttpResponse.json(SUMMARY)),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring-settings"), ({ params }) =>
      settings
        ? HttpResponse.json({
            cohort_id: String(params.cohort_id),
            allow_team_mentoring: true,
            allow_1_on_1: true,
            default_1on1_minutes: 120,
            default_team_minutes: 0,
            min_lead_hours: 24,
            allowed_duration: 60,
            max_pending_requests: 1,
            weekday_hours: { start: "10:00", end: "19:00" },
            weekend_hours: null,
            updated_at: "2026-11-20T01:00:00Z",
          })
        : HttpResponse.json(
            { error: { code: "mentoring_settings_not_configured", message: "설정이 필요합니다." } },
            { status: 404 },
          ),
    ),
    http.get(apiUrl("/api/v1/admin/teams"), () =>
      HttpResponse.json([
        {
          id: "t1",
          department_id: "d1",
          name: "교육운영 1팀",
          description: null,
          bootcamp_ids: ["b1"],
          employee_count: 3,
        },
        { id: "t2", department_id: "d1", name: "교육운영 2팀", description: null, bootcamp_ids: [], employee_count: 2 },
      ]),
    ),
    http.patch(apiUrl("/api/v1/admin/cohorts/{cohort_id}"), async ({ request }) => {
      const body = (await request.json()) as Partial<Cohort>;
      patches.push({ path: "cohort", body });
      return HttpResponse.json({ ...C12, ...body });
    }),
    http.patch(apiUrl("/api/v1/admin/bootcamps/{bootcamp_id}"), async ({ request }) => {
      const body = (await request.json()) as Partial<Bootcamp>;
      patches.push({ path: "bootcamp", body });
      return HttpResponse.json({ ...BE, ...body });
    }),
    http.put(apiUrl("/api/v1/admin/bootcamps/{bootcamp_id}/team"), async ({ request }) => {
      const body = await request.json();
      puts.push(body);
      return HttpResponse.json({ bootcamp_id: "b1", team_id: "t2" });
    }),
  );
  return { patches, puts };
}

describe("학사 > 과정·기수 (FE-17a)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("과정 목록(사용 중 먼저)과 첫 과정의 기수 표, 보관 기수는 숨김", async () => {
    mockApi();
    await renderRoute("/admin/academy/bootcamps");
    const list = await screen.findByRole("navigation", { name: "과정" });
    const links = within(list).getAllByRole("link");
    expect(links.map((l) => l.textContent)).toEqual([
      "백엔드 부트캠프BE",
      "프론트엔드 부트캠프FE",
      "CEO 과정CEO사용 안 함",
    ]);
    expect(links[0]).toHaveAttribute("aria-current", "page");
    const table = await screen.findByRole("table", { name: "기수" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => r.getAttribute("aria-label"))).toEqual(["12기", "11기"]);
    expect(rows[0]).toHaveTextContent("2026.06.02 ~ 2026.11.30진행 중AIGb1 · 12회차1203948576612345678");
    const menu = screen.getByRole("navigation", { name: "메뉴" });
    expect(within(menu).getByRole("link", { name: "과정·기수" })).toHaveAttribute("aria-current", "page");
  });

  it("다른 과정을 누르면 그 과정의 기수를 읽는다", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/academy/bootcamps");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: /프론트엔드 부트캠프/ }));
    await waitFor(() => expect(router.state.location.search).toEqual({ bootcamp: "b3" }));
    expect(await screen.findByText("기수가 없어요")).toBeInTheDocument();
  });

  it("기수 패널: 기본 정보·운영·수강생·멘토·담당자·멘토링 설정", async () => {
    mockApi();
    await renderRoute("/admin/academy/bootcamps?bootcamp=b1&cohort=c12");
    const sheet = await screen.findByRole("dialog", { name: "12기" });
    expect(await within(sheet).findByRole("region", { name: "수강생 34명" })).toHaveTextContent(
      "가입28명수강 중30명수료0명중도 포기2명조기 취업1명기수 이동1명",
    );
    expect(within(sheet).getByRole("list", { name: "멘토" })).toHaveTextContent("이멘토11/2부터");
    expect(within(sheet).getByRole("list", { name: "담당자" })).toHaveTextContent(
      "박매니저운영 매니저 · 기수최팀장팀장 · 과정",
    );
    expect(await within(sheet).findByRole("region", { name: "멘토링 설정" })).toHaveTextContent(
      "신청 유형1:1 · 팀진행 단위60분신청 마감24시간 전평일10:00~19:00주말·공휴일운영 안 함",
    );
  });

  it("멘토링 설정이 없으면 '설정 전', 조회 권한이 없으면 섹션이 없다", async () => {
    mockApi({ settings: false });
    await renderRoute("/admin/academy/bootcamps?bootcamp=b1&cohort=c12");
    let sheet = await screen.findByRole("dialog", { name: "12기" });
    expect(await within(sheet).findByText("설정 전이에요.")).toBeInTheDocument();

    mockApi({ codes: ["academy.bootcamp.read", "academy.cohort.read"] });
    await renderRoute("/admin/academy/bootcamps?bootcamp=b1&cohort=c11");
    sheet = await screen.findByRole("dialog", { name: "11기" });
    await within(sheet).findByRole("region", { name: "수강생 34명" });
    expect(within(sheet).queryByRole("region", { name: "멘토링 설정" })).not.toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "수정" })).not.toBeInTheDocument();
  });

  it("기수 운영 항목 수정: 바뀐 값만 보낸다, 숫자가 아니면 오류", async () => {
    const { patches } = mockApi();
    await renderRoute("/admin/academy/bootcamps?bootcamp=b1&cohort=c12");
    const sheet = await screen.findByRole("dialog", { name: "12기" });
    const user = userEvent.setup();
    await user.click(await within(sheet).findByRole("button", { name: "수정" }));
    const form = within(sheet).getByRole("form", { name: "기수 수정" });
    const discord = within(form).getByRole("textbox", { name: "디스코드 서버" });
    await user.clear(discord);
    await user.type(discord, "abc");
    await user.click(within(form).getByRole("button", { name: "저장" }));
    expect(await within(form).findByText("숫자만 적어 주세요.")).toBeInTheDocument();
    await user.clear(discord);
    await user.click(within(form).getByRole("combobox", { name: "상태" }));
    await user.click(await screen.findByRole("option", { name: "비활성" }));
    await user.click(within(form).getByRole("button", { name: "저장" }));
    await waitFor(() =>
      expect(patches).toEqual([{ path: "cohort", body: { status: "INACTIVE", discord_guild_id: null } }]),
    );
    expect(await screen.findByText("백엔드 부트캠프 12기를 저장했어요")).toBeInTheDocument();
  });

  it("과정 정보: 사용 여부·Airtable 별칭·담당 팀을 바꾼다", async () => {
    const { patches, puts } = mockApi();
    await renderRoute("/admin/academy/bootcamps?bootcamp=b1&panel=bootcamp");
    const sheet = await screen.findByRole("dialog", { name: "백엔드 부트캠프" });
    expect(await within(sheet).findByText("교육운영 1팀")).toBeInTheDocument();
    expect(within(sheet).getByText("AIGb1 · 백엔드 부트캠프 HRD")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    const form = within(sheet).getByRole("form", { name: "과정 수정" });
    await user.click(within(form).getByRole("switch", { name: "사용 여부" }));
    await user.clear(within(form).getByRole("textbox", { name: "기수 별칭" }));
    await user.click(within(form).getByRole("combobox", { name: "담당 팀" }));
    await user.click(await screen.findByRole("option", { name: "교육운영 2팀" }));
    await user.click(within(form).getByRole("button", { name: "저장" }));
    await waitFor(() =>
      expect(patches).toEqual([{ path: "bootcamp", body: { is_active: false, airtable_cohort_prefix: null } }]),
    );
    expect(puts).toEqual([{ team_id: "t2" }]);
    expect(await screen.findByText("백엔드 부트캠프 과정을 저장했어요")).toBeInTheDocument();
  });

  it("팀 조회 권한이 없으면 담당 팀 줄이 없다", async () => {
    mockApi({ codes: ["academy.bootcamp.read", "academy.bootcamp.manage", "academy.cohort.read"] });
    await renderRoute("/admin/academy/bootcamps?bootcamp=b1&panel=bootcamp");
    const sheet = await screen.findByRole("dialog", { name: "백엔드 부트캠프" });
    await within(sheet).findByText("기수 별칭");
    expect(within(sheet).queryByText("담당 팀")).not.toBeInTheDocument();
  });
});
