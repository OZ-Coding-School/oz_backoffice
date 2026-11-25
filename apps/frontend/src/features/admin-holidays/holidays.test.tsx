import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { Holiday } from "./api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });

const pub = (holiday_date: string, name: string): Holiday => ({ id: null, holiday_date, name, source: "PUBLIC" });
const HOLIDAYS: Holiday[] = [
  pub("2026-01-01", "1월1일"),
  pub("2026-08-15", "광복절"),
  pub("2026-08-17", "대체공휴일"),
  { id: "c1", holiday_date: "2026-07-01", name: "창립기념일", source: "CUSTOM" },
];

function access(codes: string[]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [],
  };
}

function mockApi({
  codes = ["mentoring.settings.read", "mentoring.settings.manage"],
  syncedAt = "2026-11-24T18:00:00Z" as string | null,
} = {}) {
  const years: string[] = [];
  const created: unknown[] = [];
  const deleted: string[] = [];
  let syncs = 0;
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/admin/mentoring-holidays"), ({ request }) => {
      const year = new URL(request.url).searchParams.get("year") ?? "";
      years.push(year);
      return HttpResponse.json({
        items: year === "2026" ? HOLIDAYS : [],
        synced_at: year === "2026" ? syncedAt : null,
      });
    }),
    http.post(apiUrl("/api/v1/admin/mentoring-holidays"), async ({ request }) => {
      const body = (await request.json()) as { holiday_date: string; name: string };
      created.push(body);
      if (body.name === "중복")
        return HttpResponse.json(
          { error: { code: "holiday_already_exists", message: "이미 등록된 휴일입니다." } },
          { status: 409 },
        );
      return HttpResponse.json({ id: "c2", ...body, source: "CUSTOM" }, { status: 201 });
    }),
    http.delete(apiUrl("/api/v1/admin/mentoring-holidays/{holiday_id}"), ({ params }) => {
      deleted.push(String(params.holiday_id));
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(apiUrl("/api/v1/admin/mentoring-holidays/sync"), () => {
      syncs += 1;
      return HttpResponse.json({
        years: [
          { year: 2026, synced_at: "2026-11-25T01:00:00Z", holiday_count: 22 },
          { year: 2027, synced_at: "2026-11-25T01:00:00Z", holiday_count: 24 },
        ],
      });
    }),
  );
  return { years, created, deleted, syncs: () => syncs };
}

describe("설정 > 공휴일 (FE-16)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("12개월 달력·범례·동기화 시각, 날짜를 고르지 않으면 그해 공휴일 목록", async () => {
    mockApi();
    await renderRoute("/admin/settings/holidays?year=2026");
    const august = await screen.findByRole("region", { name: "8월" });
    expect(screen.getAllByRole("region", { name: /^\d+월$/ })).toHaveLength(12);
    expect(within(august).getByRole("link", { name: "8월 15일 광복절" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "범례" })).toHaveTextContent("법정공휴일 3일추가 휴일 1일");
    expect(screen.getByText("법정공휴일 마지막 동기화 11/25 03:00")).toBeInTheDocument();
    const all = screen.getByRole("list", { name: "2026년 공휴일" });
    expect(within(all).getAllByRole("listitem")).toHaveLength(4);
    expect(screen.queryByRole("region", { name: "선택한 날" })).not.toBeInTheDocument();
    const menu = screen.getByRole("navigation", { name: "메뉴" });
    expect(within(menu).getByRole("link", { name: "공휴일" })).toHaveAttribute("aria-current", "page");
  });

  it("법정공휴일을 고르면 구분·이름·삭제 불가만 보인다", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/settings/holidays?year=2026");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: "8월 17일 대체공휴일" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ year: 2026, date: "2026-08-17" }));
    const panel = screen.getByRole("region", { name: "선택한 날" });
    expect(panel).toHaveTextContent("2026년 8월 17일 (월)");
    expect(panel).toHaveTextContent("구분법정공휴일");
    expect(panel).toHaveTextContent("이름대체공휴일");
    expect(panel).toHaveTextContent("삭제불가");
    expect(within(panel).queryByRole("button")).not.toBeInTheDocument();
  });

  it("평일을 고르면 이름을 적어 추가 휴일로 등록한다 (409는 필드 아래)", async () => {
    const { created } = mockApi();
    await renderRoute("/admin/settings/holidays?year=2026&date=2026-06-05");
    const panel = await screen.findByRole("region", { name: "선택한 날" });
    expect(panel).toHaveTextContent("구분평일");
    const user = userEvent.setup();
    const submit = within(panel).getByRole("button", { name: "추가 휴일로 등록" });
    expect(submit).toBeDisabled();
    const input = within(panel).getByRole("textbox", { name: "휴일 이름" });
    await user.type(input, "중복");
    await user.click(submit);
    expect(await within(panel).findByText("이미 등록된 휴일입니다.")).toBeInTheDocument();
    await user.clear(input);
    await user.type(input, "임시 휴무");
    await user.click(submit);
    await waitFor(() => expect(created.at(-1)).toEqual({ holiday_date: "2026-06-05", name: "임시 휴무" }));
    expect(await screen.findByText("6/5 (금) 임시 휴무를 추가 휴일로 등록했어요")).toBeInTheDocument();
  });

  it("추가 휴일은 확인 창을 거쳐 지운다", async () => {
    const { deleted } = mockApi();
    await renderRoute("/admin/settings/holidays?year=2026&date=2026-07-01");
    const panel = await screen.findByRole("region", { name: "선택한 날" });
    expect(panel).toHaveTextContent("구분추가 휴일");
    expect(panel).toHaveTextContent("삭제가능");
    const user = userEvent.setup();
    await user.click(within(panel).getByRole("button", { name: "추가 휴일 삭제" }));
    const dialog = await screen.findByRole("dialog", { name: "창립기념일을 지울까요?" });
    await user.click(within(dialog).getByRole("button", { name: "삭제" }));
    await waitFor(() => expect(deleted).toEqual(["c1"]));
    expect(await screen.findByText("창립기념일을 지웠어요")).toBeInTheDocument();
  });

  it("[지금 가져오기]는 연도별 건수를 알린다, 아직 받지 않은 해는 안내", async () => {
    const { syncs } = mockApi({ syncedAt: null });
    await renderRoute("/admin/settings/holidays?year=2026");
    expect(await screen.findByText("법정공휴일을 아직 가져오지 않았어요")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "지금 가져오기" }));
    expect(await screen.findByText("법정공휴일을 가져왔어요 (2026년 22일 · 2027년 24일)")).toBeInTheDocument();
    expect(syncs()).toBe(1);
  });

  it("연도를 넘기면 그해를 다시 조회한다", async () => {
    const { years } = mockApi();
    const { router } = await renderRoute("/admin/settings/holidays?year=2026");
    await screen.findByRole("region", { name: "1월" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("link", { name: "다음 해" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ year: 2027 }));
    await waitFor(() => expect(years.at(-1)).toBe("2027"));
    expect(await screen.findByText("공휴일이 없어요.")).toBeInTheDocument();
  });

  it("조회 권한만 있으면 등록·삭제·가져오기가 없다", async () => {
    mockApi({ codes: ["mentoring.settings.read"] });
    await renderRoute("/admin/settings/holidays?year=2026&date=2026-07-01");
    const panel = await screen.findByRole("region", { name: "선택한 날" });
    expect(within(panel).queryByRole("button", { name: "추가 휴일 삭제" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "지금 가져오기" })).not.toBeInTheDocument();
  });
});
