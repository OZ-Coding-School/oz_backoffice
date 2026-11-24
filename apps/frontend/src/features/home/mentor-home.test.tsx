import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { makeThread, mockChat } from "@/features/chat/test-utils";
import type { MentoringRequest } from "@/features/requests/api";
import { makeRequest } from "@/features/requests/test-utils";
import type { MentoringSession } from "@/features/sessions/api";
import { makeSession } from "@/features/sessions/test-utils";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { desiredSummary } from "./mentor-api";

const MENTOR = makeMe({
  id: "u9",
  name: "김멘토",
  account_type: "MENTOR",
  roles: [{ role: "MENTOR", scope_type: "GLOBAL", scope_id: null, expires_at: null }],
});

const NOW = new Date("2026-11-20T03:00:00Z"); // 11/20(금) 12:00 KST

const TODAY = makeSession(); // 11/20 14:00~15:00 KST, Meet 링크
const LIVE = makeSession({
  id: "s0",
  status: "IN_PROGRESS",
  topic: "팀 프로젝트 API 설계 리뷰",
  team_id: "t3",
  team_label: "3팀 알파",
  starts_at: "2026-11-20T02:30:00Z",
  ends_at: "2026-11-20T03:30:00Z",
});
const LATER = makeSession({
  id: "s2",
  topic: "이력서 첨삭",
  requester_name: "나수강",
  starts_at: "2026-11-24T10:00:00Z",
  ends_at: "2026-11-24T11:00:00Z",
});
const MISSING = makeSession({
  id: "s9",
  topic: "ORM 최적화",
  requester_name: "다수강",
  starts_at: "2026-11-13T06:00:00Z",
  ends_at: "2026-11-13T07:00:00Z",
});

const COUNTS = { SCHEDULED: 3, IN_PROGRESS: 1, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 };

function page(items: MentoringSession[], recordMissing: number) {
  return {
    items,
    total: items.length,
    limit: 3,
    offset: 0,
    counts: COUNTS,
    view_counts: { upcoming: 3, record_missing: recordMissing, past: 0, all: 3 + recordMissing },
  };
}

function mockHome({
  recordMissing = 1,
  pending = [
    makeRequest(),
    makeRequest({ id: "r2", topic: "팀 배포 점검", team_id: "t3", team_label: "3팀 알파", desired_times: [] }),
  ],
  accepting = true,
}: { recordMissing?: number; pending?: MentoringRequest[]; accepting?: boolean } = {}) {
  const seen: URLSearchParams[] = [];
  const put: unknown[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/mentor-sessions"), ({ request }) => {
      const params = new URL(request.url).searchParams;
      seen.push(params);
      if (params.get("view") === "record_missing") return HttpResponse.json(page([MISSING], recordMissing));
      if (params.get("from")) return HttpResponse.json({ ...page([LIVE, TODAY], recordMissing), total: 2 });
      return HttpResponse.json(page([LIVE, TODAY, LATER], recordMissing));
    }),
    http.get(apiUrl("/api/v1/me/mentor-requests"), () =>
      HttpResponse.json({
        items: pending,
        total: pending.length,
        limit: 3,
        offset: 0,
        counts: { PENDING: pending.length + 2, APPROVED: 0, REJECTED: 0, CANCELED: 0 },
      }),
    ),
    http.get(apiUrl("/api/v1/me/mentor-schedule"), () =>
      HttpResponse.json({ mentor_id: "m1", accepting_requests: accepting, unavailable_periods: [] }),
    ),
    http.put(apiUrl("/api/v1/me/mentor-schedule/accepting"), async ({ request }) => {
      const body = (await request.json()) as { accepting_requests: boolean };
      put.push(body);
      return HttpResponse.json({ accepting_requests: body.accepting_requests, canceled_pending_requests: 2 });
    }),
  );
  mockChat([makeThread({ unread_count: 2 })]);
  return { seen, put };
}

describe("멘토 홈 표시 (F57)", () => {
  it("희망 수와 가장 이른 희망 (KST)", () => {
    expect(desiredSummary(makeRequest({ desired_times: ["2026-11-25T10:00:00Z", "2026-11-24T10:00:00Z"] }))).toBe(
      "희망 2개 · 가장 이른 11/24(화) 19:00",
    );
    expect(desiredSummary(makeRequest({ desired_times: [] }))).toBe("희망 0개");
  });
});

describe("멘토 홈 (F57)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(NOW);
    resetAuth();
    mockSignedIn(MENTOR);
  });

  afterEach(() => vi.useRealTimers());

  it("요약 4칸은 각 화면으로 가고, 오늘은 KST 하루로 센다", async () => {
    const { seen } = mockHome();
    await renderRoute("/");
    const summary = await screen.findByRole("list", { name: "할 일 요약" });
    const link = (name: RegExp) => within(summary).getByRole("link", { name });
    await waitFor(() => expect(link(/처리할 신청/)).toHaveTextContent("4건"));
    expect(link(/처리할 신청/)).toHaveAttribute("href", "/mentor/requests");
    expect(link(/오늘 세션/)).toHaveTextContent("2회");
    expect(link(/기록 미제출/)).toHaveAttribute("href", "/mentor/sessions?tab=record_missing");
    expect(link(/기록 미제출/)).toHaveTextContent("1회");
    expect(link(/안 읽은 채팅/)).toHaveTextContent("2개");
    const today = seen.find((p) => p.get("from"));
    expect([today?.get("from"), today?.get("to")]).toEqual(["2026-11-19T15:00:00.000Z", "2026-11-20T15:00:00.000Z"]);
    expect(today?.getAll("status")).toEqual(["SCHEDULED", "IN_PROGRESS"]);
  });

  it("기록 미제출이 하나면 그 세션으로 [기록 작성], 여럿이면 [모두 보기]", async () => {
    mockHome();
    const { unmount } = await renderRoute("/");
    expect(await screen.findByText("기록하지 않은 세션이 1회 있어요")).toBeInTheDocument();
    expect(await screen.findByText(/11\/13\(금\) 15:00 ORM 최적화\(다수강 · 1:1\)/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "기록 작성" })).toHaveAttribute("href", "/mentor/sessions/s9");
    unmount();

    mockHome({ recordMissing: 3 });
    await renderRoute("/");
    expect(await screen.findByText("기록하지 않은 세션이 3회 있어요")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "모두 보기" })).toHaveAttribute(
      "href",
      "/mentor/sessions?tab=record_missing",
    );
  });

  it("기록 미제출이 없으면 경고가 없다", async () => {
    mockHome({ recordMissing: 0 });
    await renderRoute("/");
    await screen.findByRole("list", { name: "할 일 요약" });
    await waitFor(() =>
      expect(
        within(screen.getByRole("list", { name: "할 일 요약" })).getByRole("link", { name: /기록 미제출/ }),
      ).toHaveTextContent("0회"),
    );
    expect(screen.queryByText(/기록하지 않은 세션이/)).not.toBeInTheDocument();
  });

  it("오늘·다가오는 세션: 진행 중·오늘은 Meet 입장, 그 밖은 배지만", async () => {
    mockHome();
    await renderRoute("/");
    const card = await screen.findByRole("region", { name: "오늘·다가오는 세션" });
    const items = await within(card).findAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("3팀 알파 · 팀 · 오늘 11:30~12:30");
    expect(within(items[0]!).getByText("진행 중")).toBeInTheDocument();
    expect(within(items[0]!).getByRole("link", { name: "Meet 입장" })).toBeInTheDocument();
    expect(within(items[1]!).getByText("오늘")).toBeInTheDocument();
    expect(within(items[1]!).getByRole("link", { name: "Meet 입장" })).toHaveAttribute(
      "href",
      "https://meet.google.com/abc-defg-hij",
    );
    expect(items[2]).toHaveTextContent("나수강 · 1:1 · 11/24(화) 19:00~20:00");
    expect(within(items[2]!).queryByRole("link", { name: "Meet 입장" })).not.toBeInTheDocument();
    expect(within(items[2]!).getByRole("link", { name: /이력서 첨삭/ })).toHaveAttribute("href", "/mentor/sessions/s2");
  });

  it("처리할 신청: 신청자·희망 수·가장 이른 희망, 없으면 안내", async () => {
    mockHome();
    const { unmount } = await renderRoute("/");
    const card = await screen.findByRole("region", { name: "처리할 신청" });
    const first = await within(card).findByRole("link", { name: /Django ORM 질문/ });
    expect(first).toHaveAttribute("href", "/mentor/requests/r1");
    expect(first).toHaveTextContent("가수강 · 희망 2개 · 가장 이른 11/24(화) 19:00");
    expect(within(card).getByRole("link", { name: /팀 배포 점검/ })).toHaveTextContent("3팀 알파 · 희망 0개");
    unmount();

    mockHome({ pending: [] });
    await renderRoute("/");
    expect(await screen.findByText("처리할 신청이 없어요.")).toBeInTheDocument();
  });

  it("신청 받기는 끌 때 확인한다", async () => {
    vi.useRealTimers();
    const { put } = mockHome();
    await renderRoute("/");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("switch", { name: "신청 받기" }));
    await user.click(await screen.findByRole("button", { name: "끄기" }));
    await waitFor(() => expect(put).toEqual([{ accepting_requests: false }]));
    expect(await screen.findByText("신청 받기를 껐어요. 대기 중인 신청 2건을 취소했어요")).toBeInTheDocument();
  });
});
