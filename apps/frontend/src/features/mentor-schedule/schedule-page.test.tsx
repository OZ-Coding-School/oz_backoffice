import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { makeSession } from "@/features/sessions/test-utils";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

const MENTOR = makeMe({
  id: "u9",
  name: "김멘토",
  account_type: "MENTOR",
  is_super_admin: false,
});

const NOW = new Date("2026-11-24T03:00:00Z"); // 11/24(화) 12:00 KST

const PERIODS = [
  {
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
  },
];

function mockSchedule(accepting = true) {
  const sessionQueries: URLSearchParams[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/mentor-schedule"), () =>
      HttpResponse.json({ mentor_id: "m1", accepting_requests: accepting, unavailable_periods: PERIODS }),
    ),
    http.get(apiUrl("/api/v1/me/mentor-sessions"), ({ request }) => {
      const params = new URL(request.url).searchParams;
      sessionQueries.push(params);
      const items =
        params.get("from") === "2026-11-22T15:00:00.000Z"
          ? [makeSession({ starts_at: "2026-11-24T10:00:00Z", ends_at: "2026-11-24T11:00:00Z" })]
          : [];
      return HttpResponse.json({
        items,
        total: items.length,
        limit: 100,
        offset: 0,
        counts: { SCHEDULED: 1, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 },
        view_counts: { upcoming: 1, record_missing: 0, past: 0, all: 1 },
      });
    }),
  );
  return sessionQueries;
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  resetAuth();
  mockSignedIn(MENTOR);
});

afterEach(() => vi.useRealTimers());

describe("멘토 일정 (F51·F52)", () => {
  it("이번 주 시간표에 매주 불가 시간 회차와 내 세션을, 목록에 등록한 불가 시간을 보여 준다", async () => {
    const queries = mockSchedule();
    await renderRoute("/mentor/schedule");
    expect(await screen.findByRole("heading", { name: "11월 23일 ~ 29일" })).toBeInTheDocument();
    expect(queries[0]?.get("from")).toBe("2026-11-22T15:00:00.000Z");
    expect(queries[0]?.get("to")).toBe("2026-11-29T15:00:00.000Z");

    const monday = screen.getByRole("group", { name: "11월 23일 (월)" });
    expect(within(monday).queryByText("본업 · 매주")).not.toBeInTheDocument();
    const tuesday = screen.getByRole("group", { name: "11월 24일 (화)" });
    expect(within(tuesday).getByText("본업 · 매주")).toBeInTheDocument();
    expect(await within(tuesday).findByRole("link", { name: "가수강 · 1:1" })).toHaveAttribute(
      "href",
      "/mentor/sessions/s1",
    );

    const list = screen.getByRole("region", { name: "등록한 불가 시간" });
    expect(within(list).getByText("매주 화·수·목·금 09:00~12:00 · 12/31까지")).toBeInTheDocument();
    expect(within(list).getByText("회사 근무")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "11월 24일 (화)" })).toHaveAttribute("aria-selected", "true");
  });

  it("다음 주로 넘기면 그 주를 부른다", async () => {
    const queries = mockSchedule();
    const { router } = await renderRoute("/mentor/schedule");
    await userEvent.setup().click(await screen.findByRole("button", { name: "다음 주" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ week: "2026-11-30" }));
    expect(await screen.findByRole("heading", { name: "11월 30일 ~ 12월 6일" })).toBeInTheDocument();
    expect(queries.at(-1)?.get("from")).toBe("2026-11-29T15:00:00.000Z");
  });

  it("신청 받기를 끌 때는 확인 창 뒤에 끄고 취소 건수를 알린다", async () => {
    mockSchedule(true);
    const bodies: unknown[] = [];
    server.use(
      http.put(apiUrl("/api/v1/me/mentor-schedule/accepting"), async ({ request }) => {
        const body = (await request.json()) as { accepting_requests: boolean };
        bodies.push(body);
        return HttpResponse.json({
          mentor_id: "m1",
          accepting_requests: body.accepting_requests,
          canceled_pending_requests: 2,
        });
      }),
    );
    await renderRoute("/mentor/schedule");
    const user = userEvent.setup();
    const toggle = await screen.findByRole("switch", { name: "신청 받기" });
    expect(toggle).toBeChecked();
    await user.click(toggle);
    const dialog = await screen.findByRole("dialog", { name: "신청 받기를 끌까요?" });
    expect(bodies).toEqual([]);
    await user.click(within(dialog).getByRole("button", { name: "끄기" }));
    await waitFor(() => expect(bodies).toEqual([{ accepting_requests: false }]));
    expect(await screen.findByText("신청 받기를 껐어요. 대기 중인 신청 2건을 취소했어요")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "신청 받기" })).not.toBeChecked();
  });

  it("켜기는 확인 없이 바로 켠다", async () => {
    mockSchedule(false);
    const bodies: unknown[] = [];
    server.use(
      http.put(apiUrl("/api/v1/me/mentor-schedule/accepting"), async ({ request }) => {
        const body = (await request.json()) as { accepting_requests: boolean };
        bodies.push(body);
        return HttpResponse.json({ mentor_id: "m1", accepting_requests: true, canceled_pending_requests: 0 });
      }),
    );
    await renderRoute("/mentor/schedule");
    await userEvent.setup().click(await screen.findByRole("switch", { name: "신청 받기" }));
    await waitFor(() => expect(bodies).toEqual([{ accepting_requests: true }]));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
