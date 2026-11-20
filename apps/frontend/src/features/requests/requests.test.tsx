import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { makeRequest, mockBalances, mockRequestDetail, mockRequestList, mockSettings } from "./test-utils";

const SESSION = { id: "s1", starts_at: "2026-11-24T10:00:00Z", ends_at: "2026-11-24T11:00:00Z" };

beforeEach(() => {
  resetAuth();
  mockSignedIn(makeMe());
  mockBalances();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("신청 내역 목록 (F29)", () => {
  it("탭마다 건수를 보여 주고, 반려·취소 탭은 상태 두 개로 조회한다", async () => {
    const seen = mockRequestList([
      makeRequest(),
      makeRequest({
        id: "r2",
        status: "APPROVED",
        topic: "포트폴리오 리뷰",
        session: SESSION,
        balance: { state: "USED", minutes: 60 },
      }),
      makeRequest({
        id: "r3",
        status: "CANCELED",
        topic: "이력서 첨삭",
        cancel_reason: "일정이 바뀌었어요",
        canceled_at: "2026-11-06T03:30:00Z",
        canceled_by: "REQUESTER",
        balance: { state: "RETURNED", minutes: 60 },
      }),
    ]);
    const user = userEvent.setup();
    await renderRoute("/mentoring/requests");

    const tabs = await screen.findByRole("navigation", { name: "신청 상태" });
    expect(within(tabs).getByRole("link", { name: "전체 3" })).toHaveAttribute("aria-current", "page");
    expect(within(tabs).getByRole("link", { name: "반려·취소 1" })).toBeInTheDocument();
    const pending = screen.getByRole("link", { name: "Django ORM 질문 · 승인 대기" });
    expect(within(pending).getByText("차감 예정 1시간")).toBeInTheDocument();
    expect(within(pending).getByText("1순위 11/24(화) 19:00 ~ 20:00")).toBeInTheDocument();
    expect(await within(pending).findByText("가수강 (나)")).toBeInTheDocument();
    const approved = screen.getByRole("link", { name: "포트폴리오 리뷰 · 승인" });
    expect(within(approved).getByText("11/24(화) 19:00 ~ 20:00")).toBeInTheDocument();
    expect(within(approved).getByText("1시간 차감")).toBeInTheDocument();
    expect(screen.getByText("취소 사유 · 일정이 바뀌었어요 (11/06 12:30 본인 취소)")).toBeInTheDocument();

    await user.click(within(tabs).getByRole("link", { name: "반려·취소 1" }));
    await waitFor(() => expect(seen.at(-1)?.status).toEqual(["REJECTED", "CANCELED"]));
    expect(await screen.findByRole("link", { name: "이력서 첨삭 · 취소" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Django ORM 질문 · 승인 대기" })).not.toBeInTheDocument();
  });

  it("신청이 없으면 빈 상태, 고른 탭에만 없으면 그 상태가 없다고 알려 준다", async () => {
    mockRequestList([], { PENDING: 0, APPROVED: 0, REJECTED: 0, CANCELED: 0 });
    await renderRoute("/mentoring/requests");
    expect(await screen.findByRole("heading", { name: "아직 보낸 신청이 없어요" })).toBeInTheDocument();
  });

  it("고른 탭에만 없으면 그 상태가 없다고 알려 준다", async () => {
    mockRequestList([makeRequest()]);
    await renderRoute("/mentoring/requests?tab=approved");
    expect(await screen.findByRole("heading", { name: "이 상태의 신청이 없어요" })).toBeInTheDocument();
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
    const many = Array.from({ length: 25 }, (_, i) => makeRequest({ id: `r${i}`, topic: `질문 ${i + 1}` }));
    const seen = mockRequestList(many, { PENDING: 25, APPROVED: 0, REJECTED: 0, CANCELED: 0 });
    await renderRoute("/mentoring/requests");
    expect(await screen.findByRole("link", { name: "질문 20 · 승인 대기" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "질문 21 · 승인 대기" })).not.toBeInTheDocument();
    observers.at(-1)?.([{ isIntersecting: true }]);
    expect(await screen.findByRole("link", { name: "질문 25 · 승인 대기" })).toBeInTheDocument();
    expect(new Set(seen.map((s) => s.offset))).toEqual(new Set([0, 20]));
  });

  it("불러오지 못하면 다시 시도할 수 있다", async () => {
    server.use(
      http.get(apiUrl("/api/v1/me/mentoring/requests"), () => HttpResponse.json(errorBody("x"), { status: 500 })),
    );
    await renderRoute("/mentoring/requests");
    expect(await screen.findByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });

  it("수강생 메뉴에 신청 내역이 있고, 멘토는 들어올 수 없다", async () => {
    mockRequestList([]);
    mockSignedIn(makeMe({ account_type: "MENTOR", name: "김멘토", roles: [] }));
    const { router } = await renderRoute("/mentoring/requests");
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });
});

describe("신청 상세·취소 (A66·F29)", () => {
  it("승인 대기: 희망 일시·차감 예정·마크다운 내용을 보여 주고, 사유를 적어 취소한다", async () => {
    mockRequestDetail(makeRequest());
    const cancel = vi.fn<(body: unknown) => void>();
    server.use(
      http.post(apiUrl("/api/v1/mentoring/requests/{request_id}/cancel"), async ({ request }) => {
        cancel(await request.json());
        return HttpResponse.json(
          makeRequest({
            status: "CANCELED",
            cancel_reason: "다음 주에 다시",
            canceled_at: "2026-11-17T01:00:00Z",
            canceled_by: "REQUESTER",
            balance: { state: "RETURNED", minutes: 60 },
          }),
        );
      }),
    );
    const user = userEvent.setup();
    await renderRoute("/mentoring/requests/r1");

    expect(await screen.findByRole("heading", { name: "Django ORM 질문", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("멘토가 이 중 하나로 승인해요")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "질문 정리" })).toBeInTheDocument(); // 마크다운
    expect(await screen.findByText("내 1:1 계좌 남은 시간")).toBeInTheDocument();
    expect(screen.getByText("이 신청 차감 예정")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "신청 변경" })).toHaveAttribute("href", "/mentoring/requests/r1/change"); // F32

    await user.click(screen.getByRole("button", { name: "신청 취소" }));
    const dialog = await screen.findByRole("dialog", { name: "이 신청을 취소할까요?" });
    expect(
      within(dialog).getByText("차감 예정이던 1시간을 바로 돌려받아요. 취소 후에는 되돌릴 수 없어요"),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "신청 취소" }));
    expect(await within(dialog).findByText("취소 사유를 적어 주세요.")).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText("취소 사유 (멘토에게 보여요)"), "다음 주에 다시");
    expect(within(dialog).getByText("8 / 300")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "신청 취소" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(cancel).toHaveBeenCalledWith({ reason: "다음 주에 다시" });
    expect(await screen.findByText("취소 사유 · 다음 주에 다시 (11/17 10:00 본인 취소)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "신청 취소" })).not.toBeInTheDocument();
  });

  it("승인: 확정 일시와 마감 안내, 마감 전에는 취소할 수 있다", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-20T00:00:00Z"));
    mockSettings(24);
    mockRequestDetail(makeRequest({ status: "APPROVED", session: SESSION, balance: { state: "USED", minutes: 60 } }));
    await renderRoute("/mentoring/requests/r1");
    expect(await screen.findByRole("heading", { name: "확정 일시" })).toBeInTheDocument();
    expect(screen.getByText("멘토가 1순위로 승인했어요")).toBeInTheDocument();
    expect(screen.getByText("이 신청 차감됨")).toBeInTheDocument();
    expect(await screen.findByText("시작 24시간 전까지 바꾸거나 취소할 수 있어요")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "신청 변경" })).toBeInTheDocument();
    expect(
      screen.getByText("시작 24시간 전(11/23(월) 19:00)까지 취소하면 1시간을 모두 돌려받아요"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "신청 취소" })).toBeInTheDocument();
  });

  it("승인: 마감이 지나면 버튼 대신 운영진 문의 안내", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-23T10:00:01Z"));
    mockSettings(24);
    mockRequestDetail(makeRequest({ status: "APPROVED", session: SESSION, balance: { state: "USED", minutes: 60 } }));
    await renderRoute("/mentoring/requests/r1");
    expect(await screen.findByText("취소 마감이 지났어요. 운영진에게 문의해 주세요.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "신청 취소" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "신청 변경" })).not.toBeInTheDocument();
  });

  it("서버가 마감 지남으로 거절하면 창 안에 알려 준다", async () => {
    mockRequestDetail(makeRequest());
    server.use(
      http.post(apiUrl("/api/v1/mentoring/requests/{request_id}/cancel"), () =>
        HttpResponse.json(errorBody("cancel_deadline_passed"), { status: 422 }),
      ),
    );
    const user = userEvent.setup();
    await renderRoute("/mentoring/requests/r1");
    await user.click(await screen.findByRole("button", { name: "신청 취소" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("취소 사유 (멘토에게 보여요)"), "사정");
    await user.click(within(dialog).getByRole("button", { name: "신청 취소" }));
    expect(await within(dialog).findByText("취소 마감이 지났어요. 운영진에게 문의해 주세요.")).toBeInTheDocument();
  });

  it("팀원이 보낸 팀 신청은 볼 수만 있다", async () => {
    mockRequestDetail(
      makeRequest({ team_id: "t1", team_label: "3팀 알파", requester_id: "other", requester_name: "나수강" }),
    );
    await renderRoute("/mentoring/requests/r1");
    expect(await screen.findByText("팀 멘토링 · 3팀 알파")).toBeInTheDocument();
    expect(screen.getByText("나수강")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "신청 취소" })).not.toBeInTheDocument();
  });

  it("반려된 신청은 사유를 보여 주고 버튼이 없다", async () => {
    mockRequestDetail(
      makeRequest({
        status: "REJECTED",
        reject_reason: "일정이 맞지 않아요",
        balance: { state: "RETURNED", minutes: 60 },
      }),
    );
    await renderRoute("/mentoring/requests/r1");
    expect(await screen.findByText("반려 사유 · 일정이 맞지 않아요")).toBeInTheDocument();
    expect(screen.queryByText("시간")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "신청 취소" })).not.toBeInTheDocument();
  });

  it("볼 수 없는 신청은 찾을 수 없다고 알려 준다", async () => {
    server.use(
      http.get(apiUrl("/api/v1/mentoring/requests/{request_id}"), () =>
        HttpResponse.json(errorBody("request_not_found"), { status: 404 }),
      ),
    );
    await renderRoute("/mentoring/requests/nope");
    expect(await screen.findByRole("heading", { name: "신청을 찾을 수 없어요" })).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByRole("link", { name: "신청 내역" })).toHaveAttribute(
      "href",
      "/mentoring/requests",
    );
  });
});
