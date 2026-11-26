import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { makeSession } from "@/features/sessions/test-utils";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { MentorItem } from "./api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });
const NOW = new Date("2026-11-24T03:00:00Z"); // 11/24(화) 12:00 KST

const MENTOR: MentorItem = {
  id: "m1",
  user_id: "u1",
  name: "김멘토",
  email: "m1@mentor.com",
  phone_number: "01011111234",
  display_name: "멘토K",
  is_active: true,
  contract_count: 1,
  created_at: "2026-11-03T01:00:00Z",
  accepting_requests: true,
  is_registered: true,
  active_cohorts: [],
};

const PERIOD = {
  id: "p1",
  mentor_id: "m1",
  repeat: "WEEKLY" as const,
  starts_at: "2026-11-03T00:00:00Z",
  ends_at: "2026-11-03T03:00:00Z",
  all_day: false,
  weekdays: [2, 3, 4, 5],
  repeat_until: "2026-12-31",
  category: "본업",
  reason: "회사 근무",
};

function access(codes = ["educator.mentor.read", "educator.mentor.manage"]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [],
  };
}

function mockApi(codes?: string[]) {
  const calls: { path: string; body: unknown }[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/admin/mentors/{mentor_id}"), () => HttpResponse.json(MENTOR)),
    http.get(apiUrl("/api/v1/admin/mentors/{mentor_id}/schedule"), () =>
      HttpResponse.json({ mentor_id: "m1", accepting_requests: true, unavailable_periods: [PERIOD] }),
    ),
    http.get(apiUrl("/api/v1/admin/mentors/{mentor_id}/sessions"), ({ request }) => {
      calls.push({ path: "sessions", body: new URL(request.url).searchParams.get("from") });
      const items = [makeSession({ starts_at: "2026-11-24T10:00:00Z", ends_at: "2026-11-24T11:00:00Z" })];
      return HttpResponse.json({ items, total: 1, limit: 100, offset: 0 });
    }),
    http.get(apiUrl("/api/v1/mentoring/holidays"), () => HttpResponse.json({ items: [] })),
    http.delete(apiUrl("/api/v1/admin/mentors/{mentor_id}/schedule/unavailable-periods/{period_id}"), ({ params }) => {
      calls.push({ path: "delete", body: params.period_id });
      return new HttpResponse(null, { status: 204 });
    }),
    http.put(apiUrl("/api/v1/admin/mentors/{mentor_id}/schedule/accepting"), async ({ request }) => {
      calls.push({ path: "accepting", body: await request.json() });
      return HttpResponse.json({ mentor_id: "m1", accepting_requests: false, canceled_pending_requests: 0 });
    }),
  );
  return calls;
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  resetAuth();
  mockSignedIn(ADMIN);
});

afterEach(() => vi.useRealTimers());

describe("강사·멘토 > 멘토 상세 > 일정 대리 (FE-18c-2)", () => {
  it("운영진 API로 그 멘토의 월 달력·개인 일정을 보여 주고, 개인 일정을 지운다", async () => {
    const calls = mockApi();
    const { router } = await renderRoute("/admin/educators/mentors/m1?tab=schedule");
    expect(await screen.findByRole("heading", { name: "2026년 11월" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "일정" })).not.toBeInTheDocument();
    const calendar = screen.getByRole("region", { name: "월 달력" });
    expect(within(calendar).getAllByRole("button", { name: "본업 · 매주 9:00" }).length).toBeGreaterThan(0);
    // 운영진 화면에는 세션 상세가 없어 세션 막대는 링크가 아니다
    expect(await within(calendar).findByRole("img", { name: "가수강 · 1:1 19:00" })).toBeInTheDocument();
    expect(within(calendar).queryByRole("link", { name: "가수강 · 1:1 19:00" })).not.toBeInTheDocument();
    expect(calls).toContainEqual({ path: "sessions", body: "2026-10-25T15:00:00.000Z" });

    const user = userEvent.setup();
    const list = screen.getByRole("region", { name: "개인 일정" });
    await user.click(within(list).getByRole("button", { name: "본업 삭제" }));
    const confirm = await screen.findByRole("dialog", { name: "이 개인 일정을 지울까요?" });
    await user.click(within(confirm).getByRole("button", { name: "지우기" }));
    await waitFor(() => expect(calls).toContainEqual({ path: "delete", body: "p1" }));

    await user.click(screen.getByRole("button", { name: "다음 달" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "schedule", month: "2026-12" }));
  });

  it("신청 받기를 끄면 운영진 API로 바꾼다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/educators/mentors/m1?tab=schedule");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("switch", { name: "신청 받기" }));
    await user.click(await screen.findByRole("button", { name: "끄기" }));
    await waitFor(() => expect(calls).toContainEqual({ path: "accepting", body: { accepting_requests: false } }));
  });

  it("멘토 관리 권한이 없으면 고칠 수 없다", async () => {
    mockApi(["educator.mentor.read"]);
    await renderRoute("/admin/educators/mentors/m1?tab=schedule");
    expect(await screen.findByRole("button", { name: "개인 일정 추가" })).toBeDisabled();
    expect(await screen.findByRole("switch", { name: "신청 받기" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "본업 수정" })).not.toBeInTheDocument();
    // 달 이동은 그대로
    expect(screen.getByRole("button", { name: "다음 달" })).toBeEnabled();
    await userEvent.setup().click(screen.getByRole("button", { name: "본업 보기" }));
    const panel = await screen.findByRole("dialog", { name: "본업" });
    expect(within(panel).queryByRole("button", { name: "수정" })).not.toBeInTheDocument();
  });
});
