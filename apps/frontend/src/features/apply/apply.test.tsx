import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { ENROLLMENTS, makeMe, MENTORING_SETTINGS, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { makeRequest, mockBalances } from "@/features/requests/test-utils";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { useApplyDraft } from "./draft";

const ONE_ON_ONE = { ...MENTORING_SETTINGS, allow_team_mentoring: false };
const MENTORS = [
  {
    mentor_id: "m1",
    display_name: "멘토K",
    headline: "네이버 백엔드 7년차",
    expertise: "Python, Django, 이력서, README",
    profile_image_url: null,
  },
  { mentor_id: "m2", display_name: "이멘토", headline: "스타트업 CTO", expertise: "FastAPI", profile_image_url: null },
];
// 11/24(화) 10:00~12:00 KST
const INTERVALS = [{ starts_at: "2026-11-24T01:00:00Z", ends_at: "2026-11-24T03:00:00Z" }];

function mockApply({ settings = ONE_ON_ONE, mentors = MENTORS }: { settings?: object; mentors?: object[] } = {}) {
  server.use(
    http.get(apiUrl("/api/v1/me/mentoring/settings"), () => HttpResponse.json(settings)),
    http.get(apiUrl("/api/v1/me/mentoring/mentors"), () => HttpResponse.json(mentors)),
    http.get(apiUrl("/api/v1/me/mentoring/mentors/{mentor_id}"), () =>
      HttpResponse.json({ ...MENTORS[0], introduction: "API를 설계·운영해 왔어요.", accepting_requests: true }),
    ),
    http.get(apiUrl("/api/v1/mentors/{mentor_id}/available-times"), () =>
      HttpResponse.json({
        mentor_id: "m1",
        cohort_id: "c12",
        accepting_requests: true,
        allowed_duration: 60,
        min_lead_hours: 24,
        intervals: INTERVALS,
      }),
    ),
  );
}

const DRAFT = {
  owner: "u1:c12",
  mentorId: "m1",
  duration: 60,
  desiredTimes: ["2026-11-24T01:00:00Z"],
  topic: "포트폴리오 리뷰",
  detail: "## 질문\n- README",
};

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-11-19T03:00:00Z"));
  sessionStorage.clear();
  useApplyDraft.setState({ owner: null, mentorId: null, duration: null, desiredTimes: [], topic: "", detail: "" });
  resetAuth();
  mockSignedIn(makeMe());
  mockBalances(120);
  mockApply();
});

afterEach(() => vi.useRealTimers());

describe("1:1 멘토링 신청 (F30)", () => {
  it("멘토 → 일정 → 신청 내용 → 확인 → 신청하면 완료 화면에서 방금 만든 신청으로 간다", async () => {
    const posted = vi.fn<(body: unknown) => void>();
    server.use(
      http.post(apiUrl("/api/v1/mentoring/requests"), async ({ request }) => {
        posted(await request.json());
        return HttpResponse.json(makeRequest({ id: "r9", topic: "포트폴리오 리뷰" }), { status: 201 });
      }),
      http.get(apiUrl("/api/v1/mentoring/requests/{request_id}"), () => HttpResponse.json(makeRequest({ id: "r9" }))),
    );
    const user = userEvent.setup();
    const { router } = await renderRoute("/mentoring/apply");

    expect(await screen.findByRole("heading", { name: "멘토를 골라 주세요" })).toBeInTheDocument();
    expect(
      await screen.findByText("지금 신청을 받는 초격차 백엔드 12기 멘토 2명이에요. 남은 1:1 시간 2시간"),
    ).toBeInTheDocument();
    expect(screen.queryByText("README")).not.toBeInTheDocument(); // 카드는 칩 앞 3개만
    const next = screen.getByRole("button", { name: "다음: 일정 선택" });
    expect(next).toBeDisabled();
    await user.click(screen.getByRole("radio", { name: /멘토K/ }));
    await user.click(next);

    expect(await screen.findByRole("heading", { name: "언제 받고 싶나요?" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "11월 24일 (화)" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "60분" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "120분" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "10:00" }));
    expect(screen.getByRole("button", { name: "10:30" })).toBeDisabled(); // 고른 시간과 겹친다
    await user.click(screen.getByRole("button", { name: "11:00" }));
    expect(screen.getByText("11/24(화) 10:00 ~ 11:00")).toBeInTheDocument();
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "다음: 신청 내용" }));

    expect(await screen.findByRole("heading", { name: "무엇을 이야기하고 싶나요?" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "다음: 신청 확인" }));
    expect(await screen.findByText("주제를 적어 주세요.")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "주제" }), "포트폴리오 리뷰");
    await user.type(screen.getByRole("textbox", { name: "상세 내용" }), "## 질문{enter}- README");
    expect(within(screen.getByLabelText("미리보기")).getByRole("heading", { name: "질문" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "다음: 신청 확인" }));

    expect(await screen.findByRole("heading", { name: "신청 내용을 확인해 주세요" })).toBeInTheDocument();
    expect(screen.getByText("1순위")).toBeInTheDocument();
    expect(screen.getByText("− 1시간")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "신청하기" }));

    expect(await screen.findByRole("heading", { name: "신청했어요" })).toBeInTheDocument();
    expect(posted).toHaveBeenCalledWith({
      cohort_id: "c12",
      mentor_id: "m1",
      team_id: null,
      topic: "포트폴리오 리뷰",
      detail: "## 질문\n- README",
      desired_times: ["2026-11-24T01:00:00.000Z", "2026-11-24T02:00:00.000Z"],
      duration: 60,
    });
    expect(router.state.location.search).toEqual({ step: "done", id: "r9" });
    expect(screen.getByRole("link", { name: "내 신청 보기" })).toHaveAttribute("href", "/mentoring/requests/r9");
    expect(useApplyDraft.getState().mentorId).toBeNull(); // 임시 값을 지운다
  });

  it("소개 모달에서 멘토를 고를 수 있다", async () => {
    const user = userEvent.setup();
    await renderRoute("/mentoring/apply");
    await user.click((await screen.findAllByRole("button", { name: "상세 소개 보기" }))[0]!);
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("API를 설계·운영해 왔어요.")).toBeInTheDocument();
    expect(within(dialog).getByText("README")).toBeInTheDocument(); // 모달은 칩 모두
    await user.click(within(dialog).getByRole("button", { name: "이 멘토 선택" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("radio", { name: /멘토K/ })).toBeChecked();
  });

  it("새로고침해도 고른 값이 남고, 서버가 대기 신청 최대 건수로 거절하면 알려 준다", async () => {
    useApplyDraft.setState(DRAFT);
    server.use(
      http.post(apiUrl("/api/v1/mentoring/requests"), () =>
        HttpResponse.json(errorBody("too_many_pending_requests"), { status: 422 }),
      ),
    );
    const user = userEvent.setup();
    await renderRoute("/mentoring/apply?step=confirm");
    expect(await screen.findByText("포트폴리오 리뷰")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "신청하기" }));
    expect(
      await screen.findByText("승인 대기 중인 신청이 최대 건수예요. 기존 신청이 처리되거나 취소한 뒤 신청해 주세요."),
    ).toBeInTheDocument();
  });

  it("희망 일시가 더는 안 되면 일정 단계로 돌아갈 수 있다", async () => {
    useApplyDraft.setState(DRAFT);
    server.use(
      http.post(apiUrl("/api/v1/mentoring/requests"), () =>
        HttpResponse.json(errorBody("desired_time_unavailable"), { status: 422 }),
      ),
    );
    const user = userEvent.setup();
    const { router } = await renderRoute("/mentoring/apply?step=confirm");
    await user.click(await screen.findByRole("button", { name: "신청하기" }));
    await user.click(await screen.findByRole("button", { name: "일정 다시 고르기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ step: "schedule" }));
  });

  it("앞 단계 값이 없으면 그 단계로 보낸다", async () => {
    const { router } = await renderRoute("/mentoring/apply?step=confirm");
    await waitFor(() => expect(router.state.location.search).toEqual({}));
    expect(await screen.findByRole("heading", { name: "멘토를 골라 주세요" })).toBeInTheDocument();
  });

  it("남은 1:1 시간이 없으면 첫머리에 알리고 다음을 막는다", async () => {
    mockBalances(30);
    await renderRoute("/mentoring/apply");
    expect(await screen.findByText("남은 1:1 시간이 없어요")).toBeInTheDocument();
    expect(await screen.findByRole("radio", { name: /멘토K/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다음: 일정 선택" })).toBeDisabled();
  });

  it("수강이 끝났으면 새 신청을 할 수 없다고 알린다", async () => {
    server.use(
      http.get(apiUrl("/api/v1/me/enrollments"), () =>
        HttpResponse.json([{ ...ENROLLMENTS[0], status: "COMPLETED", ended_at: "2027-03-31" }]),
      ),
    );
    await renderRoute("/mentoring/apply");
    expect(await screen.findByText("수강이 끝나 새 신청을 할 수 없어요")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "다음: 일정 선택" })).not.toBeInTheDocument();
  });

  it("신청 받는 멘토가 없으면 빈 상태", async () => {
    mockApply({ mentors: [] });
    await renderRoute("/mentoring/apply");
    expect(await screen.findByRole("heading", { name: "지금 신청을 받는 멘토가 없어요" })).toBeInTheDocument();
  });

  it("'멘토링 신청' 메뉴는 1:1만 허용한 기수에만 있다 (FE-3a)", async () => {
    const { unmount } = await renderRoute("/");
    const menus = await screen.findAllByRole("navigation", { name: "메뉴" });
    expect(await within(menus[0]!).findByRole("link", { name: "멘토링 신청" })).toBeInTheDocument();
    unmount();

    mockApply({ settings: MENTORING_SETTINGS }); // 1:1·팀 모두 허용 → FE-3b에서
    await renderRoute("/");
    await screen.findByRole("heading", { name: "안녕하세요, 가수강님" });
    await waitFor(() =>
      expect(within(screen.getAllByRole("navigation", { name: "메뉴" })[0]!).getAllByRole("link")).toHaveLength(2),
    );
    expect(screen.queryByRole("link", { name: "멘토링 신청" })).not.toBeInTheDocument();
  });
});
