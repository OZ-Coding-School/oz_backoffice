import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { kstDateKey } from "@/features/apply/slots";
import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { makeRequest, mockBalances, mockRequestDetail, mockSettings } from "./test-utils";

// 실제 시계로 이틀 뒤(KST) 10:00~13:00이 비어 있다 (가짜 시계와 TZDate가 겹치면 jsdom에서 시각이 어긋난다)
const day = kstDateKey(new Date(Date.now() + 2 * 86_400_000));
const at = (hm: string) => new Date(`${day}T${hm}:00+09:00`).toISOString();

beforeEach(() => {
  resetAuth();
  mockSignedIn(makeMe());
  mockBalances(60);
  mockSettings(24);
  server.use(
    http.get(apiUrl("/api/v1/mentors/{mentor_id}/available-times"), () =>
      HttpResponse.json({
        mentor_id: "m1",
        cohort_id: "c12",
        accepting_requests: true,
        allowed_duration: 60,
        min_lead_hours: 24,
        intervals: [{ starts_at: at("10:00"), ends_at: at("13:00") }],
      }),
    ),
  );
});

describe("신청 변경 (F32)", () => {
  it("기존 값으로 채우고, 고쳐서 저장하면 새 신청 상세로 간다", async () => {
    mockRequestDetail(makeRequest({ desired_times: [at("10:00")] }));
    const posted = vi.fn<(body: unknown) => void>();
    server.use(
      http.post(apiUrl("/api/v1/mentoring/requests/{request_id}/change"), async ({ request }) => {
        posted(await request.json());
        return HttpResponse.json(makeRequest({ id: "r2", topic: "바뀐 주제", replaced_request_id: "r1" }), {
          status: 201,
        });
      }),
    );
    const user = userEvent.setup();
    const { router } = await renderRoute("/mentoring/requests/r1/change");

    expect(await screen.findByRole("heading", { name: "신청 변경" })).toBeInTheDocument();
    expect(screen.getByText("멘토와 멘토링 종류는 바꿀 수 없어요")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "주제" })).toHaveValue("Django ORM 질문");
    expect(screen.getByText("1 / 3")).toBeInTheDocument(); // 기존 희망 일시
    // 기존 신청의 차감 예정 1시간을 돌려받는다고 보고 120분까지 고를 수 있다 (남은 60분 + 60분)
    expect(screen.getByRole("radio", { name: "120분" })).toBeInTheDocument();
    if (day.slice(0, 7) !== kstDateKey(new Date()).slice(0, 7)) {
      await user.click(screen.getByRole("button", { name: "다음 달로 이동" }));
    }
    await user.click(await screen.findByRole("button", { name: "12:00" }));
    await user.clear(screen.getByRole("textbox", { name: "주제" }));
    await user.type(screen.getByRole("textbox", { name: "주제" }), "바뀐 주제");
    await user.click(screen.getByRole("button", { name: "변경 저장" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/mentoring/requests/r2"));
    expect(posted).toHaveBeenCalledWith({
      topic: "바뀐 주제",
      detail: makeRequest().detail.trim(),
      desired_times: [at("10:00"), at("12:00")],
      duration: 60,
    });
    expect(await screen.findByText("신청을 바꿨어요")).toBeInTheDocument();
  });

  it("승인된 신청을 바꾸면 확정 세션이 취소된다고 알린다", async () => {
    mockRequestDetail(
      makeRequest({
        status: "APPROVED",
        desired_times: [at("10:00")],
        session: { id: "s1", starts_at: at("10:00"), ends_at: at("11:00") },
        balance: { state: "USED", minutes: 60 },
      }),
    );
    await renderRoute("/mentoring/requests/r1/change");
    expect(await screen.findByText("저장하면 확정된 세션이 취소돼요")).toBeInTheDocument();
  });

  it("서버가 희망 일시를 거절하면 알린다", async () => {
    mockRequestDetail(makeRequest({ desired_times: [at("10:00")] }));
    server.use(
      http.post(apiUrl("/api/v1/mentoring/requests/{request_id}/change"), () =>
        HttpResponse.json(errorBody("desired_time_unavailable"), { status: 422 }),
      ),
    );
    const user = userEvent.setup();
    await renderRoute("/mentoring/requests/r1/change");
    await user.click(await screen.findByRole("button", { name: "변경 저장" }));
    expect(
      await screen.findByText("고른 희망 일시 중 이제 신청할 수 없는 시간이 있어요. 일정을 다시 골라 주세요."),
    ).toBeInTheDocument();
  });

  it("팀원이 보낸 신청은 바꿀 수 없다", async () => {
    mockRequestDetail(
      makeRequest({ team_id: "t1", team_label: "3팀", requester_id: "other", requester_name: "나수강" }),
    );
    await renderRoute("/mentoring/requests/r1/change");
    const empty = await screen.findByRole("heading", { name: "이 신청은 바꿀 수 없어요" });
    expect(within(empty.parentElement!).getByText(/신청한 사람만/)).toBeInTheDocument();
  });
});
