import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { MentoringSession } from "@/features/sessions/api";
import { makeSession } from "@/features/sessions/test-utils";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { canEnterMeet, durationLabel, mentorStatus, recordState } from "./labels";

const MENTOR = makeMe({
  id: "u9",
  name: "김멘토",
  account_type: "MENTOR",
  roles: [{ role: "MENTOR", scope_type: "GLOBAL", scope_id: null, expires_at: null }],
});

const NOW = new Date("2026-11-20T03:00:00Z"); // 11/20(금) 12:00 KST
const now = NOW.getTime();

const TODAY = makeSession(); // 11/20 14:00~15:00 KST, 예정, Meet 링크
const LATER = makeSession({
  id: "s2",
  title: "3팀 알파 3회차",
  topic: "팀 프로젝트 API 설계 리뷰",
  team_id: "t3",
  team_label: "3팀 알파",
  starts_at: "2026-11-23T07:00:00Z",
  ends_at: "2026-11-23T08:00:00Z",
});
const MISSING = makeSession({
  id: "s3",
  title: "멘토K 멘토링 1회차",
  topic: "ORM 최적화",
  requester_name: "나수강",
  starts_at: "2026-11-13T06:00:00Z",
  ends_at: "2026-11-13T07:00:00Z",
});
const DONE = makeSession({
  id: "s4",
  status: "COMPLETED",
  title: "멘토K 멘토링 2회차",
  starts_at: "2026-11-16T01:00:00Z",
  ends_at: "2026-11-16T02:00:00Z",
  record_duration_minutes: 90,
  recorded_at: "2026-11-16T02:20:00Z",
});

const VIEW_COUNTS = { upcoming: 2, record_missing: 1, past: 1, all: 4 };

function mockMentorSessions(byView: Record<string, MentoringSession[]>) {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/mentor-sessions"), ({ request }) => {
      const params = new URL(request.url).searchParams;
      seen.push(params);
      const items = byView[params.get("view") ?? "all"] ?? [];
      return HttpResponse.json({
        items,
        total: items.length,
        limit: 20,
        offset: 0,
        counts: { SCHEDULED: 3, IN_PROGRESS: 0, COMPLETED: 1, NO_SHOW: 0, CANCELED: 0 },
        view_counts: params.get("cohort_id") ? { upcoming: 1, record_missing: 0, past: 0, all: 1 } : VIEW_COUNTS,
      });
    }),
    http.get(apiUrl("/api/v1/me/mentor-assignments"), () =>
      HttpResponse.json([
        {
          id: "a1",
          cohort_id: "c12",
          bootcamp_name: "초격차 백엔드",
          cohort_number: 12,
          start_date: "2026-10-01",
          end_date: "2027-03-31",
          is_active: true,
          deactivated_at: null,
          deactivation_reason: null,
          cost_settlement_policy: "PAID",
          pay_unit: "HOURLY",
          pay_rate: 50000,
          no_show_pay_amount: null,
        },
      ]),
    ),
  );
  return seen;
}

describe("멘토 세션 표시 (F47)", () => {
  it("상태 배지: 오늘·예정·진행 중·진행됨·완료", () => {
    expect(mentorStatus(TODAY, now).label).toBe("오늘");
    expect(mentorStatus(LATER, now).label).toBe("예정");
    expect(mentorStatus(TODAY, Date.parse("2026-11-20T05:30:00Z")).label).toBe("진행 중");
    expect(mentorStatus(MISSING, now).label).toBe("진행됨");
    expect(mentorStatus(DONE, now).label).toBe("완료");
  });

  it("기록 칸·시간·Meet 입장", () => {
    expect(recordState(MISSING, now)).toEqual({ kind: "missing" });
    expect(recordState(TODAY, now)).toEqual({ kind: "none" });
    expect(recordState(DONE, now)).toEqual({ kind: "submitted", label: "11/16 제출" });
    expect(durationLabel(DONE)).toBe("60분 → 90분");
    expect(durationLabel(TODAY)).toBe("60분");
    expect(canEnterMeet(TODAY, now)).toBe(true);
    expect(canEnterMeet(LATER, now)).toBe(false); // 오늘이 아니다
    expect(canEnterMeet(MISSING, now)).toBe(false); // 이미 끝났다
  });
});

describe("멘토 세션 목록 (F46·A77)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(NOW);
    resetAuth();
    mockSignedIn(MENTOR);
  });

  afterEach(() => vi.useRealTimers());

  it("기본은 다가오는 탭(이른 순)이고 탭 건수와 행을 보여 준다", async () => {
    const seen = mockMentorSessions({ upcoming: [TODAY, LATER] });
    await renderRoute("/mentor/sessions");
    expect(await screen.findByRole("heading", { name: "세션", level: 1 })).toBeInTheDocument();
    const tabs = screen.getByRole("navigation", { name: "세션 구분" });
    expect(await within(tabs).findByRole("link", { name: "다가오는 2" })).toHaveAttribute("aria-current", "page");
    expect(within(tabs).getByRole("link", { name: "기록 미제출 1" })).toHaveAttribute(
      "href",
      "/mentor/sessions?tab=record_missing",
    );
    expect([seen[0]?.get("view"), seen[0]?.get("order")]).toEqual(["upcoming", "asc"]);

    const table = screen.getByRole("table");
    const row = within(table).getByRole("row", { name: /멘토K 멘토링 3회차/ });
    expect(row).toHaveTextContent("11/20(금) 14:00");
    expect(row).toHaveTextContent("가수강 · 1:1");
    expect(within(row).getByText("오늘")).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: "Meet 입장" })).toHaveAttribute(
      "href",
      "https://meet.google.com/abc-defg-hij",
    );
    const team = within(table).getByRole("row", { name: /3팀 알파 3회차/ });
    expect(team).toHaveTextContent("3팀 알파 · 팀");
    expect(within(team).queryByRole("link", { name: "Meet 입장" })).not.toBeInTheDocument();
    expect(screen.getByRole("article", { name: "멘토K 멘토링 3회차" })).toHaveTextContent("기록 —");
  });

  it("기록 미제출 탭은 최신순이고 미제출 배지를, 지난 세션은 제출일을 보여 준다", async () => {
    const seen = mockMentorSessions({ record_missing: [MISSING], past: [DONE] });
    await renderRoute("/mentor/sessions?tab=record_missing");
    const row = await screen.findByRole("row", { name: /멘토K 멘토링 1회차/ });
    expect(within(row).getByText("진행됨")).toBeInTheDocument();
    expect(within(row).getByText("미제출")).toBeInTheDocument();
    expect(seen[0]?.get("order")).toBeNull();

    await userEvent.setup().click(screen.getByRole("link", { name: "지난 세션 1" }));
    const done = await screen.findByRole("row", { name: /멘토K 멘토링 2회차/ });
    expect(done).toHaveTextContent("60분 → 90분");
    expect(done).toHaveTextContent("11/16 제출");
  });

  it("기수를 고르면 그 기수로 거르고 탭 건수도 따른다", async () => {
    const seen = mockMentorSessions({ upcoming: [TODAY] });
    const { router } = await renderRoute("/mentor/sessions");
    await screen.findByRole("link", { name: "다가오는 2" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("combobox", { name: "기수" }));
    await user.click(await screen.findByRole("option", { name: "초격차 백엔드 12기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ cohort: "c12" }));
    expect(await screen.findByRole("link", { name: "다가오는 1" })).toBeInTheDocument();
    expect(seen.at(-1)?.get("cohort_id")).toBe("c12");
  });

  it("세션이 없으면 빈 상태를 보여 준다", async () => {
    server.use(
      http.get(apiUrl("/api/v1/me/mentor-sessions"), () =>
        HttpResponse.json({
          items: [],
          total: 0,
          limit: 20,
          offset: 0,
          counts: { SCHEDULED: 0, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 },
          view_counts: { upcoming: 0, record_missing: 0, past: 0, all: 0 },
        }),
      ),
      http.get(apiUrl("/api/v1/me/mentor-assignments"), () => HttpResponse.json([])),
    );
    await renderRoute("/mentor/sessions");
    expect(await screen.findByRole("heading", { name: "아직 세션이 없어요" })).toBeInTheDocument();
  });
});
