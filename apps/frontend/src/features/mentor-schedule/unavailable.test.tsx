import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { UnavailablePeriod } from "./schedule";

const MENTOR = makeMe({
  id: "u9",
  name: "김멘토",
  account_type: "MENTOR",
  is_super_admin: false,
});
const NOW = new Date("2026-11-24T03:00:00Z"); // 11/24(화) 12:00 KST

const WEEKLY: UnavailablePeriod = {
  id: "p1",
  mentor_id: "m1",
  repeat: "WEEKLY",
  starts_at: "2026-11-03T00:00:00Z",
  ends_at: "2026-11-03T03:00:00Z",
  all_day: false,
  weekdays: [2, 3, 4, 5],
  repeat_until: "2026-12-31",
  category: "본업",
  reason: null,
};
const STARTED: UnavailablePeriod = {
  ...WEEKLY,
  id: "p2",
  repeat: "ONCE",
  starts_at: "2026-11-23T10:00:00Z",
  ends_at: "2026-11-23T12:00:00Z",
  weekdays: [],
  repeat_until: null,
  category: "강의",
};

function mockSchedule(periods: UnavailablePeriod[] = [WEEKLY, STARTED]) {
  server.use(
    http.get(apiUrl("/api/v1/me/mentor-schedule"), () =>
      HttpResponse.json({ mentor_id: "m1", accepting_requests: true, unavailable_periods: periods }),
    ),
    http.get(apiUrl("/api/v1/me/mentor-sessions"), () =>
      HttpResponse.json({
        items: [],
        total: 0,
        limit: 100,
        offset: 0,
        counts: { SCHEDULED: 0, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 },
        view_counts: { upcoming: 0, record_missing: 0, past: 0, all: 0 },
      }),
    ),
  );
}

const CONFLICTS = [
  {
    kind: "REQUEST",
    target_id: "r1",
    starts_at: "2026-11-24T10:00:00Z",
    ends_at: "2026-11-24T11:00:00Z",
    topic: "Django ORM 질문",
    requester_label: "가수강",
  },
];

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  resetAuth();
  mockSignedIn(MENTOR);
});

afterEach(() => vi.useRealTimers());

describe("불가 시간 추가·수정·삭제 (F53)", () => {
  it("매주 불가 시간을 추가하고, 충돌이면 확인 뒤 confirm으로 다시 보낸다", async () => {
    mockSchedule([]);
    const calls: { confirm: string | null; body: Record<string, unknown> }[] = [];
    server.use(
      http.post(apiUrl("/api/v1/me/mentor-schedule/unavailable-periods"), async ({ request }) => {
        const confirm = new URL(request.url).searchParams.get("confirm");
        const body = (await request.json()) as Record<string, unknown>;
        calls.push({ confirm, body });
        const applied = confirm === "true";
        return HttpResponse.json(
          { applied, unavailable_period: { ...WEEKLY, id: "p9" }, conflicts: CONFLICTS },
          { status: applied ? 201 : 200 },
        );
      }),
    );
    await renderRoute("/mentor/schedule");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "불가 시간 추가" }));
    const dialog = await screen.findByRole("dialog", { name: "불가 시간 추가" });
    await user.click(within(dialog).getByRole("radio", { name: "매주" }));
    expect(within(dialog).queryByRole("checkbox", { name: "하루 종일" })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "저장" }));
    expect(await within(dialog).findByText("요일을 하나 이상 골라 주세요.")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "화" }));
    await user.click(within(dialog).getByRole("button", { name: "목" }));
    await user.click(within(dialog).getByRole("button", { name: "본업" }));
    await user.click(within(dialog).getByRole("button", { name: "저장" }));

    const conflict = await screen.findByRole("dialog", { name: "겹치는 일정이 1건 있어요" });
    expect(within(conflict).getByText("Django ORM 질문")).toBeInTheDocument();
    expect(within(conflict).getByText("가수강 · 11/24(화) 19:00 희망")).toBeInTheDocument();
    expect(within(conflict).getByText("대기 신청 → 반려")).toBeInTheDocument();
    await user.click(within(conflict).getByRole("button", { name: "그래도 저장" }));
    expect(await screen.findByText("저장했어요. 겹친 일정 1건을 정리했어요")).toBeInTheDocument();
    expect(calls.map((c) => c.confirm)).toEqual(["false", "true"]);
    expect(calls[0]?.body).toMatchObject({
      repeat: "WEEKLY",
      weekdays: [2, 4],
      starts_at: "2026-11-24T00:00:00.000Z",
      ends_at: "2026-11-24T01:00:00.000Z",
      category: "본업",
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("하루 종일 한 번은 첫 날·마지막 날만 받는다", async () => {
    mockSchedule([]);
    const bodies: unknown[] = [];
    server.use(
      http.post(apiUrl("/api/v1/me/mentor-schedule/unavailable-periods"), async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ applied: true, unavailable_period: WEEKLY, conflicts: [] }, { status: 201 });
      }),
    );
    await renderRoute("/mentor/schedule");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "불가 시간 추가" }));
    const dialog = await screen.findByRole("dialog", { name: "불가 시간 추가" });
    await user.click(within(dialog).getByRole("checkbox", { name: "하루 종일" }));
    expect(within(dialog).queryByRole("combobox", { name: "시작 시각" })).not.toBeInTheDocument();
    const last = within(dialog).getByLabelText("마지막 날");
    await user.clear(last);
    await user.type(last, "2026-11-26");
    await user.click(within(dialog).getByRole("button", { name: "저장" }));
    await waitFor(() =>
      expect(bodies).toEqual([
        {
          repeat: "ONCE",
          all_day: true,
          start_date: "2026-11-24",
          end_date: "2026-11-26",
          weekdays: [],
          category: null,
          reason: null,
        },
      ]),
    );
    expect(await screen.findByText("불가 시간을 추가했어요")).toBeInTheDocument();
  });

  it("목록 ⋯ 메뉴로 고치고 지운다. 이미 시작한 한 번은 메뉴가 없다", async () => {
    mockSchedule();
    const puts: unknown[] = [];
    const deletes: string[] = [];
    server.use(
      http.put(apiUrl("/api/v1/me/mentor-schedule/unavailable-periods/{period_id}"), async ({ request, params }) => {
        puts.push({ id: params.period_id, body: await request.json() });
        return HttpResponse.json({ applied: true, unavailable_period: WEEKLY, conflicts: [] });
      }),
      http.delete(apiUrl("/api/v1/me/mentor-schedule/unavailable-periods/{period_id}"), ({ params }) => {
        deletes.push(String(params.period_id));
        return new HttpResponse(null, { status: 204 });
      }),
    );
    await renderRoute("/mentor/schedule");
    const user = userEvent.setup();
    const list = await screen.findByRole("region", { name: "등록한 불가 시간" });
    expect(within(list).queryByRole("button", { name: "강의 메뉴" })).not.toBeInTheDocument();

    await user.click(within(list).getByRole("button", { name: "본업 메뉴" }));
    await user.click(await screen.findByRole("menuitem", { name: "수정" }));
    const dialog = await screen.findByRole("dialog", { name: "불가 시간 수정" });
    expect(within(dialog).getByRole("button", { name: "화" })).toHaveAttribute("aria-pressed", "true");
    expect(within(dialog).getByLabelText("반복 종료 (선택)")).toHaveValue("2026-12-31");
    await user.click(within(dialog).getByRole("button", { name: "저장" }));
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0]).toMatchObject({
      id: "p1",
      body: { repeat: "WEEKLY", weekdays: [2, 3, 4, 5], repeat_until: "2026-12-31" },
    });

    await user.click(within(list).getByRole("button", { name: "본업 메뉴" }));
    await user.click(await screen.findByRole("menuitem", { name: "삭제" }));
    const confirm = await screen.findByRole("dialog", { name: "이 불가 시간을 지울까요?" });
    await user.click(within(confirm).getByRole("button", { name: "지우기" }));
    await waitFor(() => expect(deletes).toEqual(["p1"]));
  });

  it("시간표의 불가 시간 블록을 누르면 수정 창이 열린다", async () => {
    mockSchedule();
    await renderRoute("/mentor/schedule");
    const tuesday = await screen.findByRole("group", { name: "11월 24일 (화)" });
    await userEvent.setup().click(within(tuesday).getByRole("button", { name: "본업 · 매주 수정" }));
    expect(await screen.findByRole("dialog", { name: "불가 시간 수정" })).toBeInTheDocument();
  });

  it("서버 오류는 문구로 안내한다", async () => {
    mockSchedule([]);
    server.use(
      http.post(apiUrl("/api/v1/me/mentor-schedule/unavailable-periods"), () =>
        HttpResponse.json(errorBody("mentor_inactive"), { status: 422 }),
      ),
    );
    await renderRoute("/mentor/schedule");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "불가 시간 추가" }));
    const dialog = await screen.findByRole("dialog", { name: "불가 시간 추가" });
    await user.click(within(dialog).getByRole("button", { name: "저장" }));
    expect(
      await within(dialog).findByText("비활성 멘토는 일정을 바꿀 수 없어요. 운영진에게 문의해 주세요."),
    ).toBeInTheDocument();
  });
});
