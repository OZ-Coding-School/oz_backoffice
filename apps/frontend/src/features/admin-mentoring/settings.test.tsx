import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess, StaffCohort } from "@/features/staff/api";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { BlockTime, MentoringSettings } from "./api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });

const COHORTS: StaffCohort[] = [
  {
    id: "c12",
    bootcamp_id: "b1",
    bootcamp_name: "백엔드 부트캠프",
    cohort_number: 12,
    start_date: "2026-09-01",
    end_date: "2027-02-28",
    status: "ONGOING",
  },
  {
    id: "c11",
    bootcamp_id: "b1",
    bootcamp_name: "백엔드 부트캠프",
    cohort_number: 11,
    start_date: "2026-03-01",
    end_date: "2026-08-31",
    status: "ENDED",
  },
  {
    id: "c3",
    bootcamp_id: "b2",
    bootcamp_name: "데이터 분석 부트캠프",
    cohort_number: 3,
    start_date: "2026-10-01",
    end_date: "2027-03-31",
    status: "ONGOING",
  },
];

const SETTINGS: MentoringSettings = {
  cohort_id: "c12",
  allow_1_on_1: true,
  allow_team_mentoring: true,
  allowed_duration: 60,
  default_1on1_minutes: 240,
  default_team_minutes: 360,
  max_pending_requests: 3,
  min_lead_hours: 24,
  weekday_hours: { start: "10:00", end: "22:00" },
  weekend_hours: null,
  updated_at: "2026-11-02T05:10:00Z",
};

const BLOCK: BlockTime = {
  id: "bt1",
  cohort_id: "c12",
  period_start: "2026-11-01",
  period_end: "2026-12-20",
  start_time: "09:00",
  end_time: "18:00",
  reason: "정규 수업",
  weekdays_only: true,
};

function access(codes = ["mentoring.settings.read", "mentoring.settings.manage"], cohortIds?: string[]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({
      code,
      is_global: !cohortIds,
      bootcamp_ids: [],
      cohort_ids: cohortIds ?? [],
    })),
    cohorts: COHORTS,
  };
}

function mockApi(opts: { settings?: MentoringSettings | null; access?: StaffAccess } = {}) {
  const calls: { method: string; body: unknown }[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(opts.access ?? access())),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring-settings"), ({ params }) =>
      opts.settings === null
        ? HttpResponse.json(errorBody("mentoring_settings_not_configured"), { status: 404 })
        : HttpResponse.json({ ...(opts.settings ?? SETTINGS), cohort_id: String(params.cohort_id) }),
    ),
    http.put(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring-settings"), async ({ request, params }) => {
      const body = (await request.json()) as Record<string, unknown>;
      calls.push({ method: "PUT", body });
      return HttpResponse.json({ ...SETTINGS, ...body, cohort_id: String(params.cohort_id) });
    }),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring-block-times"), () => HttpResponse.json([BLOCK])),
    http.post(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring-block-times"), async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      calls.push({ method: "POST", body });
      if (body.period_start === "2026-11-03")
        return HttpResponse.json(errorBody("block_time_overlap"), { status: 409 });
      return HttpResponse.json({ ...BLOCK, ...body, id: "bt2" }, { status: 201 });
    }),
    http.delete(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring-block-times/{block_id}"), ({ params }) => {
      calls.push({ method: "DELETE", body: params.block_id });
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return calls;
}

beforeEach(() => {
  resetAuth();
  mockSignedIn(ADMIN);
  try {
    localStorage.clear();
  } catch {
    // 저장소가 없어도 테스트는 이어 간다
  }
});

describe("멘토링 > 멘토링 설정 (FE-19a)", () => {
  it("메뉴 주소는 진행 중인 첫 기수로 보내고, 저장한 설정을 보여 준 뒤 바꾼 것을 저장한다", async () => {
    const calls = mockApi();
    const { router } = await renderRoute("/admin/mentoring/settings");
    await waitFor(() => expect(router.state.location.pathname).toBe("/admin/cohorts/c12/mentoring/settings"));
    expect(await screen.findByRole("heading", { level: 1, name: "멘토링 설정" })).toBeInTheDocument();
    expect(screen.getByText("마지막 저장 11월 2일 14:10")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "현재 기수" })).toHaveTextContent("백엔드 부트캠프 12기");

    // 바뀐 것이 없으면 저장 막대가 없다
    expect(screen.queryByRole("button", { name: "저장" })).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "60분" })).toBeChecked();
    expect(screen.getByLabelText("기본 지급 · 1:1")).toHaveValue("4");
    expect(screen.getByRole("switch", { name: "주말·공휴일 운영" })).not.toBeChecked();

    const user = userEvent.setup();
    await user.click(screen.getByRole("radio", { name: "2건" }));
    const grant = screen.getByLabelText("기본 지급 · 팀");
    await user.clear(grant);
    await user.type(grant, "8");
    await user.click(screen.getByRole("switch", { name: "주말·공휴일 운영" }));
    expect(screen.getByText("저장하지 않은 변경이 있어요")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0]?.body).toEqual({
      allow_1_on_1: true,
      allow_team_mentoring: true,
      allowed_duration: 60,
      default_1on1_minutes: 240,
      default_team_minutes: 480,
      max_pending_requests: 2,
      min_lead_hours: 24,
      weekday_hours: { start: "10:00", end: "22:00" },
      weekend_hours: { start: "10:00", end: "18:00" },
    });
    expect(await screen.findByText("멘토링 설정을 저장했어요")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("button", { name: "저장" })).not.toBeInTheDocument());
  });

  it("아직 저장하지 않은 기수는 기본값과 안내를 보여 주고 그대로 저장할 수 있다. 방식은 하나 이상", async () => {
    const calls = mockApi({ settings: null });
    await renderRoute("/admin/cohorts/c12/mentoring/settings");
    expect(await screen.findByText("아직 저장하지 않은 기수예요")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("switch", { name: "1:1 멘토링" }));
    await user.click(screen.getByRole("button", { name: "저장" }));
    expect(await screen.findByText("1:1과 팀 멘토링 중 하나 이상을 허용해 주세요.")).toBeInTheDocument();
    expect(calls).toEqual([]);
    await user.click(screen.getByRole("switch", { name: "1:1 멘토링" }));
    await user.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() =>
      expect(calls[0]?.body).toMatchObject({ allow_1_on_1: true, weekday_hours: { start: "10:00", end: "19:00" } }),
    );
  });

  it("현재 기수를 바꾸면 같은 화면의 그 기수로 간다", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/cohorts/c12/mentoring/settings");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "현재 기수" }));
    const popover = await screen.findByRole("dialog", { name: "기수 고르기" });
    await user.type(within(popover).getByRole("textbox", { name: "과정·기수 검색" }), "데이터");
    expect(within(popover).queryByRole("button", { name: "백엔드 부트캠프 11기" })).not.toBeInTheDocument();
    await user.click(within(popover).getByRole("button", { name: "데이터 분석 부트캠프 3기" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/admin/cohorts/c3/mentoring/settings"));
    expect(localStorage.getItem("oz.admin.current-cohort")).toBe("c3");
  });

  it("기수 선택기: 왼쪽 과정 · 오른쪽 기수, 종료 기수는 켜야 보이고 최근 고른 기수는 칩으로 (F94)", async () => {
    mockApi();
    localStorage.setItem("oz.admin.recent-cohorts", JSON.stringify(["c3"]));
    await renderRoute("/admin/cohorts/c12/mentoring/settings");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "현재 기수" }));
    const popover = await screen.findByRole("dialog", { name: "기수 고르기" });
    const backend = within(popover).getByRole("group", { name: "백엔드 부트캠프 기수" });
    expect(within(backend).getByRole("button", { name: "백엔드 부트캠프 12기" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(backend).queryByRole("button", { name: "백엔드 부트캠프 11기" })).not.toBeInTheDocument();
    await user.click(within(popover).getByRole("switch", { name: "종료된 기수도 보기" }));
    expect(within(popover).getByRole("button", { name: "백엔드 부트캠프 11기" })).toBeInTheDocument();
    expect(within(popover).getByRole("button", { name: "최근 데이터 분석 부트캠프 3기" })).toBeInTheDocument();
    await user.click(within(popover).getByRole("button", { name: /데이터 분석 부트캠프/, pressed: false }));
    expect(
      within(within(popover).getByRole("group", { name: "데이터 분석 부트캠프 기수" })).getByRole("button", {
        name: "데이터 분석 부트캠프 3기",
      }),
    ).toBeInTheDocument();
  });

  it("금지 시간대: 점선 카드로 추가하고(겹치면 안내), 항목 패널에서 지운다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/cohorts/c12/mentoring/settings");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "금지 시간대 추가" }));
    const panel = await screen.findByRole("dialog", { name: "금지 시간대 추가" });
    await user.type(within(panel).getByLabelText("시작 날짜"), "2026-11-03");
    await user.type(within(panel).getByLabelText("끝 날짜"), "2026-11-10");
    await user.click(within(panel).getByRole("button", { name: "저장" }));
    expect(await within(panel).findByText("같은 기간·시간대에 이미 금지 시간대가 있어요.")).toBeInTheDocument();
    // 설정 폼은 제출되지 않는다
    expect(calls.map((c) => c.method)).toEqual(["POST"]);
    await user.click(within(panel).getByRole("button", { name: "닫기" }));

    await user.click(screen.getByRole("button", { name: /11.1 ~ 12.20 · 09:00 ~ 18:00/ }));
    const view = await screen.findByRole("dialog", { name: "금지 시간대" });
    expect(within(view).getByText("2026.11.01 ~ 2026.12.20")).toBeInTheDocument();
    await user.click(within(view).getByRole("button", { name: "삭제" }));
    await user.click(
      within(await screen.findByRole("dialog", { name: "이 금지 시간대를 지울까요?" })).getByRole("button", {
        name: "지우기",
      }),
    );
    await waitFor(() => expect(calls).toContainEqual({ method: "DELETE", body: "bt1" }));
  });

  it("관리 권한이 없는 기수는 조회만 (저장·추가·수정 없음)", async () => {
    mockApi({ access: access(["mentoring.settings.read"]) });
    await renderRoute("/admin/cohorts/c12/mentoring/settings");
    expect(await screen.findByRole("heading", { level: 1, name: "멘토링 설정" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "저장" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "금지 시간대 추가" })).not.toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "1:1 멘토링" })).toBeDisabled();
    await userEvent.setup().click(screen.getByRole("button", { name: /11.1 ~ 12.20/ }));
    const view = await screen.findByRole("dialog", { name: "금지 시간대" });
    expect(within(view).queryByRole("button", { name: "수정" })).not.toBeInTheDocument();
  });

  it("볼 기수가 없으면 안내", async () => {
    mockApi({ access: { ...access(), cohorts: [] } });
    await renderRoute("/admin/mentoring/settings");
    expect(await screen.findByText("볼 수 있는 기수가 없어요")).toBeInTheDocument();
  });
});
