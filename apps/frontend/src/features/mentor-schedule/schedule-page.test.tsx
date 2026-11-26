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
        params.get("from") === "2026-10-25T15:00:00.000Z"
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
    http.get(apiUrl("/api/v1/mentoring/holidays"), ({ request }) => {
      const from = new URL(request.url).searchParams.get("from");
      return HttpResponse.json({
        items: from === "2026-11-30" ? [{ holiday_date: "2026-12-25", name: "기독탄신일", source: "PUBLIC" }] : [],
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

describe("멘토 일정 월 달력 (F51·F89)", () => {
  it("이번 달 달력에 반복 개인 일정을 이어진 막대로, 세션을 그날에, 목록에 등록한 개인 일정을 보여 준다", async () => {
    const queries = mockSchedule();
    await renderRoute("/mentor/schedule");
    expect(await screen.findByRole("heading", { name: "2026년 11월" })).toBeInTheDocument();
    expect(queries[0]?.get("from")).toBe("2026-10-25T15:00:00.000Z");
    expect(queries[0]?.get("to")).toBe("2026-12-06T15:00:00.000Z");

    const calendar = screen.getByRole("region", { name: "월 달력" });
    // 매주 화~금 → 한 주에 막대 하나 (11/3 주 ~ 12/1 주 다섯 줄, 12/31까지)
    expect(within(calendar).getAllByRole("button", { name: "본업 · 매주 9:00" })).toHaveLength(5);
    expect(await within(calendar).findByRole("link", { name: "가수강 · 1:1 19:00" })).toHaveAttribute(
      "href",
      "/mentor/sessions/s1",
    );

    const list = screen.getByRole("region", { name: "개인 일정" });
    expect(within(list).getByText("매주 화·수·목·금 09:00~12:00 · 12/31까지")).toBeInTheDocument();
    expect(within(list).getByText("회사 근무")).toBeInTheDocument();
    // 휴대폰 작은 달력: 오늘이 골라져 있고 그날 목록
    expect(screen.getByRole("button", { name: "11월 24일 (화)" })).toHaveAttribute("aria-pressed", "true");
    expect(
      within(screen.getByRole("region", { name: "고른 날 일정" })).getByText("11/24(화) · 2건"),
    ).toBeInTheDocument();
  });

  it("다음 달로 넘기면 그 달을 부르고 공휴일을 참고로 보여 준다. [오늘]은 이번 달로", async () => {
    const queries = mockSchedule();
    const { router } = await renderRoute("/mentor/schedule");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "다음 달" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ month: "2026-12" }));
    expect(await screen.findByRole("heading", { name: "2026년 12월" })).toBeInTheDocument();
    expect(queries.at(-1)?.get("from")).toBe("2026-11-29T15:00:00.000Z");
    const christmas = screen.getByRole("group", { name: "12월 25일 (금)" });
    expect(await within(christmas).findByText("기독탄신일")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "오늘" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ month: "2026-11" }));
    expect(screen.getByRole("button", { name: "오늘" })).toBeDisabled();
  });

  it("달력의 개인 일정을 누르면 상세 패널이 열리고, [수정]은 같은 패널에서 고친다", async () => {
    mockSchedule();
    await renderRoute("/mentor/schedule");
    const user = userEvent.setup();
    const calendar = await screen.findByRole("region", { name: "월 달력" });
    const [bar] = within(calendar).getAllByRole("button", { name: "본업 · 매주 9:00" });
    await user.click(bar!);
    const panel = await screen.findByRole("dialog", { name: "본업" });
    expect(within(panel).getByText("매주 화·수·목·금")).toBeInTheDocument();
    expect(within(panel).getByText("2026.11.03 ~ 2026.12.31")).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "수정" }));
    expect(await within(panel).findByText("수정 중")).toBeInTheDocument();
    expect(within(panel).getByLabelText("반복 종료 (선택)")).toHaveValue("2026-12-31");
    await user.click(within(panel).getByRole("button", { name: "취소" }));
    expect(await within(panel).findByRole("button", { name: "수정" })).toBeInTheDocument();
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
