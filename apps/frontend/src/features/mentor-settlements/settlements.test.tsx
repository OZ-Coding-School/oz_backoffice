import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { SettlementDetail, SettlementItem, SettlementSummary } from "./api";
import { closedLabel, counterpartLabel, detailSubtitle, monthTitle, summaryCards, unitPrice, won } from "./labels";

const MENTOR = makeMe({
  id: "u9",
  name: "김멘토",
  account_type: "MENTOR",
  roles: [{ role: "MENTOR", scope_type: "GLOBAL", scope_id: null, expires_at: null }],
});

const NOW = new Date("2026-11-20T03:00:00Z"); // 2026-11-20 KST

function summary(overrides: Partial<SettlementSummary> = {}): SettlementSummary {
  return {
    id: "st1",
    mentor_id: "m1",
    mentor_name: "김멘토",
    cohort_id: "c12",
    bootcamp_name: "초격차 백엔드",
    cohort_number: 12,
    month: "2026-10",
    status: "CLOSED",
    session_count: 14,
    total_minutes: 960,
    total_amount: 480000,
    closed_at: "2026-11-05T01:00:00Z",
    ...overrides,
  };
}

const OCT_12 = summary();
const OCT_9 = summary({
  id: "st2",
  cohort_id: "c9",
  bootcamp_name: "프론트엔드",
  cohort_number: 9,
  session_count: 7,
  total_minutes: 420,
  total_amount: 570000,
});
const SEP_11 = summary({
  id: "st3",
  cohort_id: "c11",
  bootcamp_name: "초격차 백엔드",
  cohort_number: 11,
  month: "2026-09",
  session_count: 16,
  total_minutes: 990,
  total_amount: 840000,
  closed_at: "2026-10-06T01:00:00Z",
});
const DEC_LAST_YEAR = summary({ id: "st4", month: "2025-12", total_amount: 100000 });

function item(overrides: Partial<SettlementItem> = {}): SettlementItem {
  return {
    session_id: "s1",
    session_starts_at: "2026-10-28T10:00:00Z",
    session_topic: "포트폴리오 방향",
    team_label: null,
    requester_name: "가수강",
    item_type: "SESSION",
    settlement_policy: "ACTUAL_DURATION",
    billable_minutes: 60,
    pay_unit: "HOURLY",
    pay_rate: 30000,
    amount: 30000,
    uncharged_overtime_minutes: 30,
    ...overrides,
  };
}

const DETAIL: SettlementDetail = {
  ...OCT_12,
  items: [
    item(),
    item({
      session_id: "s2",
      session_starts_at: "2026-10-24T01:00:00Z",
      session_topic: "ERD 리뷰",
      team_label: "3팀 알파",
      requester_name: "가수강",
      billable_minutes: 90,
      amount: 45000,
      uncharged_overtime_minutes: null,
    }),
    item({
      session_id: "s3",
      session_starts_at: "2026-10-20T11:00:00Z",
      session_topic: "이력서",
      requester_name: "다수강",
      item_type: "NO_SHOW",
      billable_minutes: 0,
      amount: 0,
      uncharged_overtime_minutes: null,
    }),
  ],
};

describe("정산 표시 (F54)", () => {
  it("요약 3칸: 가장 최근 달 · 그 전 달 · 올해 누적", () => {
    const cards = summaryCards([OCT_12, OCT_9, SEP_11, DEC_LAST_YEAR], NOW.getTime());
    expect(cards).toEqual([
      { label: "10월 정산 합계", amount: 1050000, note: "2개 기수 · 세션 21회" },
      { label: "9월 정산 합계", amount: 840000, note: "1개 기수 · 세션 16회" },
      { label: "올해 누적", amount: 1890000, note: "3개 정산서" },
    ]);
    expect(summaryCards([], NOW.getTime())).toEqual([]);
    // 그 전 달 정산이 없으면 0원, 1월의 전 달은 지난해 12월
    expect(summaryCards([summary({ month: "2026-01" })], NOW.getTime())[1]).toEqual({
      label: "12월 정산 합계",
      amount: 0,
      note: "정산 없음",
    });
  });

  it("월·마감·단가·상대·머리 설명", () => {
    expect(monthTitle("2026-10")).toBe("2026년 10월");
    expect(closedLabel(OCT_12)).toBe("11/05 마감");
    expect(won(1234567)).toBe("1,234,567원");
    expect(unitPrice(item())).toBe("30,000원/시간");
    expect(unitPrice(item({ pay_unit: "PER_SESSION", pay_rate: 50000 }))).toBe("50,000원/회");
    expect(counterpartLabel(item())).toBe("가수강 · 1:1");
    expect(counterpartLabel(item({ team_label: "3팀 알파" }))).toBe("3팀 알파 · 팀");
    expect(detailSubtitle(DETAIL)).toBe("정산 기준 실제 진행 시간 · 30,000원/시간 · 11/05 마감");
    // 세션 항목의 단가가 여러 개면 단가는 뺀다
    expect(detailSubtitle({ ...DETAIL, items: [item(), item({ session_id: "x", pay_rate: 40000 })] })).toBe(
      "정산 기준 실제 진행 시간 · 11/05 마감",
    );
  });
});

function mockSettlements(list: SettlementSummary[]) {
  server.use(
    http.get(apiUrl("/api/v1/me/mentor-settlements"), () => HttpResponse.json(list)),
    http.get(apiUrl("/api/v1/me/mentor-settlements/{settlement_id}"), ({ params }) =>
      params.settlement_id === DETAIL.id
        ? HttpResponse.json(DETAIL)
        : HttpResponse.json({ error: { code: "not_found", message: "정산을 찾을 수 없습니다." } }, { status: 404 }),
    ),
    http.get(apiUrl("/api/v1/me/mentor-assignments"), () =>
      HttpResponse.json(
        [
          ["c12", "초격차 백엔드", 12],
          ["c9", "프론트엔드", 9],
        ].map(([cohort, name, number]) => ({
          id: `a-${cohort}`,
          cohort_id: cohort,
          bootcamp_name: name,
          cohort_number: number,
          start_date: "2026-09-01",
          end_date: null,
          is_active: true,
          deactivated_at: null,
          deactivation_reason: null,
          cost_settlement_policy: "ACTUAL_DURATION",
          pay_unit: "HOURLY",
          pay_rate: 30000,
          no_show_pay_amount: 0,
        })),
      ),
    ),
  );
}

describe("멘토 정산 화면 (F54·A80)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(NOW);
    resetAuth();
    mockSignedIn(MENTOR);
  });

  afterEach(() => vi.useRealTimers());

  it("목록: 요약 3칸과 표, 행은 정산서로 간다", async () => {
    mockSettlements([OCT_12, OCT_9, SEP_11]);
    await renderRoute("/mentor/settlements");
    expect(await screen.findByRole("heading", { name: "정산", level: 1 })).toBeInTheDocument();
    const cards = screen.getByRole("list", { name: "정산 요약" });
    expect(cards).toHaveTextContent("10월 정산 합계1,050,000원2개 기수 · 세션 21회");
    expect(cards).toHaveTextContent("올해 누적1,890,000원3개 정산서");
    const row = within(screen.getByRole("table")).getByRole("row", { name: /초격차 백엔드 12기/ });
    expect(row).toHaveTextContent("2026-10");
    expect(row).toHaveTextContent("14회");
    expect(row).toHaveTextContent("16시간");
    expect(row).toHaveTextContent("480,000원");
    expect(row).toHaveTextContent("11/05 마감");
    expect(within(row).getByRole("link", { name: "초격차 백엔드 12기" })).toHaveAttribute(
      "href",
      "/mentor/settlements/st1",
    );
    expect(screen.getByRole("article", { name: "2026-09 · 초격차 백엔드 11기" })).toHaveTextContent(
      "세션 16회 · 16시간 30분 · 10/06 마감",
    );
  });

  it("기수를 고르면 목록과 요약이 그 기수 기준이다", async () => {
    mockSettlements([OCT_12, OCT_9, SEP_11]);
    const { router } = await renderRoute("/mentor/settlements");
    await screen.findByRole("list", { name: "정산 요약" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("combobox", { name: "기수" }));
    await user.click(await screen.findByRole("option", { name: "프론트엔드 9기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ cohort: "c9" }));
    expect(screen.getByRole("list", { name: "정산 요약" })).toHaveTextContent(
      "10월 정산 합계570,000원1개 기수 · 세션 7회",
    );
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(2); // 머리 + 1
  });

  it("마감된 정산이 없으면 빈 상태", async () => {
    mockSettlements([]);
    await renderRoute("/mentor/settlements");
    expect(await screen.findByRole("heading", { name: "아직 마감된 정산이 없어요" })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "정산 요약" })).not.toBeInTheDocument();
  });

  it("상세: 머리·합계·명세, 미차감 초과는 보이지 않는다", async () => {
    mockSettlements([OCT_12]);
    await renderRoute("/mentor/settlements/st1");
    expect(
      await screen.findByRole("heading", { name: "2026년 10월 · 초격차 백엔드 12기", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText("정산 기준 실제 진행 시간 · 30,000원/시간 · 11/05 마감")).toBeInTheDocument();
    const table = screen.getByRole("table");
    const first = within(table).getByRole("row", { name: /가수강 · 1:1/ });
    expect(first).toHaveTextContent("10/28(수) 19:00");
    expect(first).toHaveTextContent("포트폴리오 방향");
    expect(first).toHaveTextContent("60분");
    expect(first).toHaveTextContent("30,000원/시간");
    expect(within(table).getByRole("row", { name: /3팀 알파 · 팀/ })).toHaveTextContent("45,000원");
    expect(within(within(table).getByRole("row", { name: /다수강/ })).getByText("노쇼")).toBeInTheDocument();
    expect(screen.queryByText(/미차감/)).not.toBeInTheDocument();
    // 뒤로 가기와 메뉴 모두 정산 목록으로 간다
    for (const link of screen.getAllByRole("link", { name: "정산" }))
      expect(link).toHaveAttribute("href", "/mentor/settlements");
  });

  it("볼 수 없는 정산서는 찾을 수 없다고 안내한다", async () => {
    mockSettlements([]);
    await renderRoute("/mentor/settlements/nope");
    expect(await screen.findByRole("heading", { name: "정산서를 찾을 수 없어요" })).toBeInTheDocument();
  });
});
