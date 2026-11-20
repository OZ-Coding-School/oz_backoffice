import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { makeCompleted, makeSession, mockArtifacts, mockSessionDetail, mockSessionList } from "./test-utils";

beforeEach(() => {
  resetAuth();
  mockSignedIn(makeMe());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const TEAM = makeCompleted({
  id: "s3",
  title: "3팀 알파 2회차",
  topic: "ERD 리뷰",
  team_id: "t3",
  team_label: "3팀 알파",
  mentor_display_name: "이멘토",
  mentor_headline: "스타트업 CTO",
  participants: [
    { student_id: "st12", name: "가수강" },
    { student_id: "st13", name: "나수강" },
  ],
});
const NO_SHOW = makeSession({ id: "s4", status: "NO_SHOW", title: "박멘토 멘토링 1회차", topic: "코딩테스트 준비" });
const CANCELED = makeSession({
  id: "s5",
  status: "CANCELED",
  title: "정멘토 멘토링 1회차",
  topic: "이력서 첨삭",
  cancel_reason: "개인 일정으로 참석이 어려워요",
  canceled_at: "2026-11-04T23:10:00Z",
  canceled_by: "REQUESTER",
  balance: { state: "RETURNED", minutes: 60 },
  google_meet_url: null,
});

describe("진행 기록 목록 (F33·A70)", () => {
  it("탭마다 건수를 보여 주고, 예정 탭은 예정·진행 중을 함께 조회한다", async () => {
    const live = makeSession({ id: "s6", status: "IN_PROGRESS", title: "멘토K 멘토링 4회차" });
    const seen = mockSessionList([makeSession(), live, makeCompleted(), TEAM, NO_SHOW, CANCELED]);
    const user = userEvent.setup();
    await renderRoute("/mentoring/sessions");

    const tabs = await screen.findByRole("navigation", { name: "세션 상태" });
    expect(within(tabs).getByRole("link", { name: "전체 5" })).toHaveAttribute("aria-current", "page");
    expect(within(tabs).getByRole("link", { name: "예정 1" })).toBeInTheDocument();
    expect(within(tabs).getByRole("link", { name: "노쇼 1" })).toBeInTheDocument();

    const scheduled = screen.getByRole("link", { name: "멘토K 멘토링 3회차 · 예정" });
    expect(within(scheduled).getByText("예약 일시")).toBeInTheDocument();
    expect(within(scheduled).getByText("14:00 ~ 15:00")).toBeInTheDocument();
    expect(within(scheduled).getByText("포트폴리오 리뷰와 README 구성")).toBeInTheDocument();
    expect(await within(scheduled).findByText("가수강 (나)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "멘토K 멘토링 4회차 · 진행 중" })).toBeInTheDocument();

    const completed = screen.getByRole("link", { name: "멘토K 멘토링 2회차 · 완료" });
    expect(within(completed).getByText("실제 진행")).toBeInTheDocument();
    expect(within(completed).getByText("10:02 ~ 11:01")).toBeInTheDocument();
    expect(within(completed).getByText("59분 · 기록 60분")).toBeInTheDocument();
    const team = screen.getByRole("link", { name: "3팀 알파 2회차 · 완료" });
    expect(within(team).getByText("팀 멘토링 · 3팀 알파")).toBeInTheDocument();
    expect(within(team).getByText("나수강")).toBeInTheDocument();

    expect(screen.getByText(/노쇼가 반복되면 멘토링 신청이 제한될 수 있어요/)).toBeInTheDocument();
    expect(
      screen.getByText("취소 사유 · 개인 일정으로 참석이 어려워요 (11/05 08:10 본인 취소, 시간 돌려받음)"),
    ).toBeInTheDocument();
    expect(scheduled).toHaveAttribute("href", "/mentoring/sessions/s1");

    await user.click(within(tabs).getByRole("link", { name: "예정 1" }));
    await waitFor(() => expect(seen.at(-1)?.status).toEqual(["SCHEDULED", "IN_PROGRESS"]));
    expect(await screen.findByRole("link", { name: "멘토K 멘토링 4회차 · 진행 중" })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByRole("link", { name: "멘토K 멘토링 2회차 · 완료" })).not.toBeInTheDocument(),
    );
  }, 20_000); // 여러 화면을 지나는 긴 흐름 (전체 실행 부하에서 5초를 넘긴 적이 있다)

  it("세션이 없으면 빈 상태, 고른 탭에만 없으면 그 상태가 없다고 알려 준다", async () => {
    mockSessionList([], { SCHEDULED: 0, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 });
    await renderRoute("/mentoring/sessions");
    expect(await screen.findByRole("heading", { name: "아직 세션이 없어요" })).toBeInTheDocument();
  });

  it("고른 탭에만 없으면 그 상태가 없다고 알려 준다", async () => {
    mockSessionList([makeSession()]);
    await renderRoute("/mentoring/sessions?tab=no_show");
    expect(await screen.findByRole("heading", { name: "이 상태의 세션이 없어요" })).toBeInTheDocument();
  });

  it("목록 끝이 보이면 다음 20개를 이어 붙인다", async () => {
    const observers: ((entries: { isIntersecting: boolean }[]) => void)[] = [];
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(cb: (entries: { isIntersecting: boolean }[]) => void) {
          observers.push(cb);
        }
        observe() {}
        disconnect() {}
      },
    );
    const many = Array.from({ length: 25 }, (_, i) => makeSession({ id: `s${i}`, title: `세션 ${i + 1}` }));
    const seen = mockSessionList(many, { SCHEDULED: 25, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 });
    await renderRoute("/mentoring/sessions");
    expect(await screen.findByRole("link", { name: "세션 20 · 예정" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "세션 21 · 예정" })).not.toBeInTheDocument();
    observers.at(-1)?.([{ isIntersecting: true }]);
    expect(await screen.findByRole("link", { name: "세션 25 · 예정" })).toBeInTheDocument();
    expect(new Set(seen.map((s) => s.offset))).toEqual(new Set([0, 20]));
  });

  it("불러오지 못하면 다시 시도할 수 있다", async () => {
    server.use(
      http.get(apiUrl("/api/v1/me/mentoring/sessions"), () => HttpResponse.json(errorBody("x"), { status: 500 })),
    );
    await renderRoute("/mentoring/sessions");
    expect(await screen.findByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });

  it("멘토는 들어올 수 없다", async () => {
    mockSessionList([]);
    mockSignedIn(makeMe({ account_type: "MENTOR", name: "김멘토", roles: [] }));
    const { router } = await renderRoute("/mentoring/sessions");
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });
});

describe("세션 상세 (F33·F34)", () => {
  it("예정: Meet 입장(새 창)과 신청 보기, 차감 예정을 보여 주고 실제 진행·멘토 기록은 없다", async () => {
    mockSessionDetail(makeSession());
    await renderRoute("/mentoring/sessions/s1");
    expect(await screen.findByRole("heading", { level: 1, name: "멘토K 멘토링 3회차" })).toBeInTheDocument();
    const meet = screen.getByRole("link", { name: "Meet 입장" });
    expect(meet).toHaveAttribute("href", "https://meet.google.com/abc-defg-hij");
    expect(meet).toHaveAttribute("target", "_blank");
    expect(meet).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByRole("link", { name: "신청 보기" })).toHaveAttribute("href", "/mentoring/requests/r1");
    expect(screen.getByText("11/20(금) 14:00 ~ 15:00")).toBeInTheDocument();
    expect(screen.getByText("차감 예정 1시간")).toBeInTheDocument();
    expect(screen.queryByText("실제 진행")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "멘토 기록" })).not.toBeInTheDocument();
    expect(screen.queryByText("신청 정보")).not.toBeInTheDocument();
  });

  it("Meet 링크가 아직 없으면 신청 보기만 있다", async () => {
    mockSessionDetail(makeSession({ google_meet_url: null }));
    await renderRoute("/mentoring/sessions/s1");
    expect(await screen.findByRole("link", { name: "신청 보기" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Meet 입장" })).not.toBeInTheDocument();
  });

  it("완료: 실제 진행·진행 시간·차감과 멘토 기록(마크다운)을 보여 주고 Meet 입장은 없다", async () => {
    mockSessionDetail(makeCompleted({ google_meet_url: "https://meet.google.com/x" }));
    mockArtifacts([]);
    await renderRoute("/mentoring/sessions/s2");
    expect(await screen.findByRole("heading", { level: 1, name: "멘토K 멘토링 2회차" })).toBeInTheDocument();
    expect(screen.getByText("10:02 ~ 11:01")).toBeInTheDocument();
    expect(screen.getByText("Meet 기록 59분")).toBeInTheDocument();
    expect(screen.getByText("1시간 차감 · 추가 차감 없음")).toBeInTheDocument();
    const record = screen.getByRole("region", { name: "멘토 기록" });
    expect(within(record).getByText("11/16 11:20 제출")).toBeInTheDocument();
    expect(within(record).getByText("README 구성")).toBeInTheDocument();
    expect(within(record).getByRole("heading", { name: "오늘 다룬 것" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Meet 입장" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "신청 보기" })).toBeInTheDocument();
  });

  it("취소: 취소 안내를 보여 준다", async () => {
    mockSessionDetail(CANCELED);
    await renderRoute("/mentoring/sessions/s5");
    expect(
      await screen.findByText("취소 사유 · 개인 일정으로 참석이 어려워요 (11/05 08:10 본인 취소, 시간 돌려받음)"),
    ).toBeInTheDocument();
    expect(screen.getByText("시간 돌려받음")).toBeInTheDocument();
  });

  it("볼 수 없는 세션은 찾을 수 없다고 알려 준다", async () => {
    server.use(
      http.get(apiUrl("/api/v1/mentoring/sessions/{session_id}"), () =>
        HttpResponse.json(errorBody("session_not_found"), { status: 404 }),
      ),
    );
    await renderRoute("/mentoring/sessions/nope");
    expect(await screen.findByRole("heading", { name: "세션을 찾을 수 없어요" })).toBeInTheDocument();
  });
});
