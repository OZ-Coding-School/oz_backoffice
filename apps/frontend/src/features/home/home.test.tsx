import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { ENROLLMENTS, makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { makeAccount } from "@/features/balances/test-utils";
import { makeThread, mockChat } from "@/features/chat/test-utils";
import { COUNTS, makeRequest, mockRequestList } from "@/features/requests/test-utils";
import type { MentoringSession } from "@/features/sessions/api";
import { makeSession } from "@/features/sessions/test-utils";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { isKstToday, kstToday } from "./api";

const NOW = new Date("2026-11-20T03:00:00Z"); // 11/20(금) 12:00 KST

const TODAY = makeSession(); // 11/20 14:00~15:00 KST, 1:1
const LATER = makeSession({
  id: "s9",
  topic: "팀 프로젝트 API 설계 리뷰",
  team_id: "t3",
  team_label: "3팀 알파",
  mentor_display_name: "이멘토",
  starts_at: "2026-11-23T07:00:00Z",
  ends_at: "2026-11-23T08:00:00Z",
});
const SESSION_COUNTS = { SCHEDULED: 2, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 };

/** 오늘 수(from·to가 있는 조회)와 다가오는 세션(order=asc)을 나눠 돌려준다 */
function mockHomeSessions(today: MentoringSession[], upcoming: MentoringSession[]) {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/mentoring/sessions"), ({ request }) => {
      const params = new URL(request.url).searchParams;
      seen.push(params);
      const items = params.has("from") ? today : upcoming;
      return HttpResponse.json({ items, total: items.length, limit: 20, offset: 0, counts: SESSION_COUNTS });
    }),
  );
  return seen;
}

function mockAccounts(
  accounts = [
    makeAccount(),
    makeAccount({
      id: "a2",
      owner_type: "TEAM",
      owner_id: "t3",
      owner_name: "3팀 알파",
      held_minutes: 0,
      remaining_minutes: 300,
    }),
  ],
) {
  server.use(http.get(apiUrl("/api/v1/me/balances"), () => HttpResponse.json(accounts)));
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  resetAuth();
  mockSignedIn(makeMe());
});

afterEach(() => vi.useRealTimers());

describe("오늘 범위 (KST)", () => {
  it("오늘 00:00~내일 00:00 KST를 UTC로 돌려준다", () => {
    expect(kstToday(NOW.getTime())).toEqual({ from: "2026-11-19T15:00:00.000Z", to: "2026-11-20T15:00:00.000Z" });
    // KST 자정 직전·직후
    expect(kstToday(Date.parse("2026-11-20T14:59:59Z")).from).toBe("2026-11-19T15:00:00.000Z");
    expect(kstToday(Date.parse("2026-11-20T15:00:00Z")).from).toBe("2026-11-20T15:00:00.000Z");
    expect(isKstToday("2026-11-20T14:59:00Z", NOW.getTime())).toBe(true);
    expect(isKstToday("2026-11-20T15:00:00Z", NOW.getTime())).toBe(false);
  });
});

describe("수강생 홈 (F42)", () => {
  it("요약 3칸은 오늘 멘토링·승인 대기 신청·안 읽은 채팅 수를 보여 주고 해당 화면으로 간다", async () => {
    const seen = mockHomeSessions([TODAY], [TODAY, LATER]);
    mockRequestList([makeRequest(), makeRequest({ id: "r2" }), makeRequest({ id: "r3" })], { ...COUNTS, PENDING: 3 });
    mockChat([makeThread({ unread_count: 2 }), makeThread({ id: "th2", unread_count: 1 })]);
    mockAccounts();
    await renderRoute("/");

    const summary = await screen.findByRole("list", { name: "할 일 요약" });
    const sessions = await within(summary).findByRole("link", { name: /오늘 멘토링\s*1회/ });
    expect(sessions).toHaveAttribute("href", "/mentoring/sessions?tab=scheduled");
    expect(await within(summary).findByRole("link", { name: /승인 대기 신청\s*3건/ })).toHaveAttribute(
      "href",
      "/mentoring/requests?tab=pending",
    );
    expect(await within(summary).findByRole("link", { name: /안 읽은 채팅\s*3개/ })).toHaveAttribute(
      "href",
      "/mentoring/chat",
    );
    // 오늘 수: 예정·진행 중, 오늘 KST 범위 / 다가오는 세션: 이른 순 3개 (A75)
    const today = seen.find((p) => p.has("from"));
    expect(today?.getAll("status")).toEqual(["SCHEDULED", "IN_PROGRESS"]);
    expect([today?.get("from"), today?.get("to")]).toEqual(["2026-11-19T15:00:00.000Z", "2026-11-20T15:00:00.000Z"]);
    const upcoming = seen.find((p) => p.get("order") === "asc");
    expect(upcoming?.get("limit")).toBe("3");
  });

  it("멘토링 카드는 남은 시간, 다가오는 세션(오늘이면 Meet 입장), 승인 대기 신청을 보여 준다", async () => {
    mockHomeSessions([TODAY], [TODAY, LATER]);
    mockRequestList([
      makeRequest({ desired_times: ["2026-11-24T10:00:00Z", "2026-11-25T10:00:00Z", "2026-11-26T10:00:00Z"] }),
    ]);
    mockAccounts();
    await renderRoute("/");

    const card = await screen.findByRole("region", { name: "멘토링" });
    expect(await within(card).findByText("3시간 30분")).toBeInTheDocument(); // 1:1 남은 시간
    expect(within(card).getByText("차감 예정 1시간")).toBeInTheDocument();
    expect(within(card).getByText("5시간")).toBeInTheDocument(); // 팀 남은 시간
    expect(within(card).getByText("3팀 알파")).toBeInTheDocument();

    const today = await within(card).findByRole("link", { name: /포트폴리오 리뷰와 README 구성/ });
    expect(today).toHaveAttribute("href", "/mentoring/sessions/s1");
    expect(today).toHaveTextContent("멘토K · 1:1 · 오늘 14:00~15:00");
    expect(within(today).getByText("오늘")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Meet 입장" })).toHaveAttribute(
      "href",
      "https://meet.google.com/abc-defg-hij",
    );

    const later = within(card).getByRole("link", { name: /팀 프로젝트 API 설계 리뷰/ });
    expect(later).toHaveTextContent("이멘토 · 3팀 알파 · 11/23(월) 16:00~17:00");
    expect(within(later).getByText("예정")).toBeInTheDocument();
    expect(within(card).getAllByRole("link", { name: "Meet 입장" })).toHaveLength(1); // 오늘 세션만

    const pending = within(card).getByRole("link", { name: /Django ORM 질문/ });
    expect(pending).toHaveAttribute("href", "/mentoring/requests/r1");
    expect(pending).toHaveTextContent("멘토K · 희망 일시 3개 · 승인 대기");
    expect(within(card).getByRole("link", { name: "멘토링 신청" })).toHaveAttribute("href", "/mentoring/apply");
  });

  it("다가오는 세션과 대기 신청이 없으면 안내와 [멘토링 신청]을 보여 준다", async () => {
    await renderRoute("/");
    const card = await screen.findByRole("region", { name: "멘토링" });
    expect(await within(card).findByText("예정된 멘토링이 없어요")).toBeInTheDocument();
    expect(within(card).getByText("아직 지급된 시간이 없어요")).toBeInTheDocument();
    expect(within(card).getAllByRole("link", { name: "멘토링 신청" })).toHaveLength(2); // 머리 링크·버튼
    expect(
      within(screen.getByRole("list", { name: "할 일 요약" })).getByRole("link", { name: /오늘 멘토링\s*0회/ }),
    ).toBeInTheDocument();
  });

  it("수강이 끝났으면 [멘토링 신청]을 숨긴다", async () => {
    server.use(
      http.get(apiUrl("/api/v1/me/enrollments"), () =>
        HttpResponse.json([{ ...ENROLLMENTS[0], status: "COMPLETED", ended_at: "2026-11-01" }]),
      ),
    );
    await renderRoute("/");
    const card = await screen.findByRole("region", { name: "멘토링" });
    expect(await within(card).findByText("예정된 멘토링이 없어요")).toBeInTheDocument();
    expect(within(card).queryByRole("link", { name: "멘토링 신청" })).not.toBeInTheDocument();
  });
});
