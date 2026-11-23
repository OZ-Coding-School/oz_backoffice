import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeStudentTeam } from "@/features/apply/team-fixture";
import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { makeAccount } from "@/features/balances/test-utils";
import { makeCompleted, makeSession } from "@/features/sessions/test-utils";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

const TEAM = makeStudentTeam({
  id: "t3",
  label: "알파",
  created_at: "2026-11-03T01:00:00Z",
  mentor: {
    mentor_id: "m2",
    display_name: "이멘토",
    headline: "스타트업 CTO · 팀 프로젝트 설계",
    expertise: "FastAPI, AWS, 설계 리뷰",
    accepting_requests: true,
  },
  members: [
    { student_id: "st12", name: "가수강", status: "ENROLLED" },
    { student_id: "st13", name: "나수강", status: "ENROLLED" },
  ],
  stats: {
    completed_sessions: 2,
    completed_minutes: 150,
    upcoming_sessions: 1,
    next_session_at: "2026-11-23T07:00:00Z",
    pending_requests: 1,
    pending_requester_name: "나수강",
  },
});

function mockTeamPage({ team = TEAM as typeof TEAM | null } = {}) {
  const seen: (string | null)[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/mentoring-teams"), () =>
      HttpResponse.json({ as_student: team ? [team] : [], as_mentor: [] }),
    ),
    http.get(apiUrl("/api/v1/me/balances"), () =>
      HttpResponse.json([
        makeAccount(),
        makeAccount({ id: "a2", owner_type: "TEAM", owner_id: "t3", total_minutes: 480, remaining_minutes: 300 }),
      ]),
    ),
    http.get(apiUrl("/api/v1/me/mentoring/sessions"), ({ request }) => {
      seen.push(new URL(request.url).searchParams.get("team_id"));
      const items = [
        makeSession({ id: "s9", title: "알파 3회차", topic: "API 설계 리뷰", team_id: "t3", team_label: "알파" }),
        makeCompleted({ id: "s8", title: "알파 2회차", topic: "ERD 리뷰", team_id: "t3", team_label: "알파" }),
      ];
      return HttpResponse.json({
        items,
        total: items.length,
        limit: 3,
        offset: 0,
        counts: { SCHEDULED: 1, IN_PROGRESS: 0, COMPLETED: 1, NO_SHOW: 0, CANCELED: 0 },
      });
    }),
    http.get(apiUrl("/api/v1/me/mentoring/mentors/{mentor_id}"), () =>
      HttpResponse.json({
        mentor_id: "m2",
        display_name: "이멘토",
        headline: "스타트업 CTO",
        expertise: "FastAPI",
        profile_image_url: null,
        introduction: "팀 프로젝트 설계를 같이 봐요.",
        accepting_requests: true,
      }),
    ),
  );
  return seen;
}

beforeEach(() => {
  resetAuth();
  mockSignedIn(makeMe());
});

describe("내 팀 (F39·A73)", () => {
  it("팀 집계·담당 멘토·팀원·최근 팀 세션을 보여 준다", async () => {
    const seen = mockTeamPage();
    const user = userEvent.setup();
    await renderRoute("/mentoring/team");

    const team = await screen.findByRole("region", { name: "알파" });
    expect(within(team).getByText("3팀")).toBeInTheDocument();
    expect(within(team).getByText("초격차 백엔드 12기 · 팀원 2명 · 11/03 구성")).toBeInTheDocument();
    expect(within(team).getByText("5시간")).toBeInTheDocument();
    expect(within(team).getByText("01/31까지 · 총 8시간 중")).toBeInTheDocument();
    expect(within(team).getByText("2회")).toBeInTheDocument();
    expect(within(team).getByText("총 2시간 30분")).toBeInTheDocument();
    expect(within(team).getByText("11/23(월) 16:00")).toBeInTheDocument();
    expect(within(team).getByText("나수강 신청")).toBeInTheDocument();

    expect(within(team).getByText("스타트업 CTO · 팀 프로젝트 설계")).toBeInTheDocument();
    expect(within(team).getByText("설계 리뷰")).toBeInTheDocument();
    expect(within(team).getByText("신청 받는 중")).toBeInTheDocument();
    const me = (await within(team).findByText("가수강")).closest("li")!;
    await waitFor(() => expect(me).toHaveTextContent("가수강나수강 중"));

    const recent = await within(team).findByRole("link", { name: "알파 3회차 · 예정" });
    expect(recent).toHaveAttribute("href", "/mentoring/sessions/s9");
    expect(within(team).getByRole("link", { name: "알파 2회차 · 완료" })).toBeInTheDocument();
    expect(seen).toContain("t3");

    expect(screen.queryByRole("link", { name: "팀 채팅" })).not.toBeInTheDocument(); // 방이 없다 (F41)
    expect(screen.getByRole("link", { name: "팀 멘토링 신청" })).toHaveAttribute("href", "/mentoring/apply?kind=team");
    await user.click(within(team).getByRole("button", { name: "상세 소개 보기" }));
    expect(await screen.findByRole("dialog", { name: "이멘토" })).toBeInTheDocument();
  });

  it("팀이 없으면 빈 상태를 보여 준다", async () => {
    mockTeamPage({ team: null });
    await renderRoute("/mentoring/team");
    expect(await screen.findByRole("heading", { name: "아직 팀에 속해 있지 않아요" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "팀 멘토링 신청" })).not.toBeInTheDocument();
  });

  it("팀 멘토링 허용 기수에 소속 팀이 있을 때만 '내 팀' 메뉴가 보인다", async () => {
    mockTeamPage();
    await renderRoute("/mentoring/team");
    const menu = (await screen.findAllByRole("navigation", { name: "메뉴" }))[0]!;
    await waitFor(() => expect(within(menu).getByRole("link", { name: "내 팀" })).toBeInTheDocument());
  });

  it("팀이 없으면 '내 팀' 메뉴가 없다", async () => {
    mockTeamPage({ team: null });
    await renderRoute("/mentoring/team");
    const menu = (await screen.findAllByRole("navigation", { name: "메뉴" }))[0]!;
    await waitFor(() => expect(within(menu).getAllByRole("link")).toHaveLength(7));
    expect(within(menu).queryByRole("link", { name: "내 팀" })).not.toBeInTheDocument();
  });
});

describe("내 팀 [팀 채팅] (F41)", () => {
  it("팀-담당 멘토 방이 있으면 바로 그 방으로 간다", async () => {
    mockTeamPage();
    server.use(
      http.get(apiUrl("/api/v1/me/mentoring/chat/threads"), () =>
        HttpResponse.json({
          items: [
            {
              id: "th-team",
              kind: "TEAM",
              cohort_id: "c12",
              student_id: null,
              student_name: null,
              team_id: "t3",
              team_label: "알파",
              mentor_id: "m2",
              mentor_display_name: "이멘토",
              last_message_at: null,
              last_message: null,
              unread_count: 0,
            },
          ],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      ),
    );
    await renderRoute("/mentoring/team");
    expect(await screen.findByRole("link", { name: "팀 채팅" })).toHaveAttribute("href", "/mentoring/chat/th-team");
  });
});
