import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { makeThread, mockChat } from "@/features/chat/test-utils";
import type { MentoringRequest } from "@/features/requests/api";
import { makeRequest } from "@/features/requests/test-utils";
import { makeSession } from "@/features/sessions/test-utils";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

const MENTOR = makeMe({
  id: "u9",
  name: "김멘토",
  account_type: "MENTOR",
  is_super_admin: false,
});

// 1순위 11/24 19:00 KST는 지났고, 2·3순위가 남았다
const NOW = new Date("2026-11-24T10:30:00Z");
const REQUEST = makeRequest({
  desired_times: ["2026-11-24T10:00:00Z", "2026-11-25T10:00:00Z", "2026-11-26T11:00:00Z"],
});

function mockDetail(request: MentoringRequest) {
  server.use(http.get(apiUrl("/api/v1/mentoring/requests/{request_id}"), () => HttpResponse.json(request)));
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  resetAuth();
  mockSignedIn(MENTOR);
});

afterEach(() => vi.useRealTimers());

describe("받은 신청 상세 (F45)", () => {
  it("머리·요약을 보여 주고, 지난 일시는 막고 남은 가장 높은 순위를 골라 승인한다", async () => {
    mockDetail(REQUEST);
    const approved: unknown[] = [];
    server.use(
      http.post(apiUrl("/api/v1/mentoring/requests/{request_id}/approve"), async ({ request }) => {
        const body = (await request.json()) as { starts_at: string };
        approved.push(body);
        const done = makeRequest({
          ...REQUEST,
          status: "APPROVED",
          session: { id: "s1", starts_at: body.starts_at, ends_at: "2026-11-25T11:00:00Z" },
        });
        return HttpResponse.json({ request: done, session: makeSession() });
      }),
    );
    await renderRoute("/mentor/requests/r1");

    expect(await screen.findByRole("heading", { name: "Django ORM 질문", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("1:1 멘토링 · 초격차 백엔드 12기")).toBeInTheDocument();
    expect(screen.getByText("초격차 백엔드 12기 · 수강 중")).toBeInTheDocument();
    expect(screen.getByText("11/26(목) 20:00 전")).toBeInTheDocument(); // 승인 기한 = 마지막 희망 일시

    const slots = screen.getByRole("radiogroup", { name: "희망 일시" });
    const first = within(slots).getByRole("radio", { name: /^1순위/ });
    expect(first).toBeDisabled();
    expect(within(slots).getByText("지난 일시예요")).toBeInTheDocument();
    expect(within(slots).getByRole("radio", { name: /^2순위 11\/25\(수\) 19:00 ~ 20:00/ })).toBeChecked();

    const user = userEvent.setup();
    await user.click(within(slots).getByRole("radio", { name: /^3순위/ }));
    await user.click(screen.getByRole("button", { name: "이 일시로 승인" }));
    expect(await screen.findByRole("heading", { name: "승인한 신청이에요" })).toBeInTheDocument();
    expect(approved).toEqual([{ starts_at: "2026-11-26T11:00:00Z" }]);
    expect(screen.getByText(/11\/26\(목\) 20:00 ~ .* · 3순위/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "반려" })).not.toBeInTheDocument();
  });

  it("승인이 다른 세션과 겹치면 그 일시를 막고 다른 일시를 고르게 한다 (409)", async () => {
    mockDetail(REQUEST);
    server.use(
      http.post(apiUrl("/api/v1/mentoring/requests/{request_id}/approve"), () =>
        HttpResponse.json(errorBody("mentor_schedule_conflict"), { status: 409 }),
      ),
    );
    await renderRoute("/mentor/requests/r1");
    await userEvent.setup().click(await screen.findByRole("button", { name: "이 일시로 승인" }));

    expect(await screen.findByText("다른 세션과 겹쳐 승인하지 못했어요. 다른 일시를 골라 주세요.")).toBeInTheDocument();
    const slots = screen.getByRole("radiogroup", { name: "희망 일시" });
    expect(within(slots).getByText("다른 세션과 겹쳐요")).toBeInTheDocument();
    expect(within(slots).getByRole("radio", { name: /^2순위/ })).toBeDisabled();
    expect(within(slots).getByRole("radio", { name: /^3순위/ })).toBeChecked();
  });

  it("반려는 사유가 필요하고, 반려하면 처리 결과를 보여 준다", async () => {
    mockDetail(REQUEST);
    const reasons: unknown[] = [];
    server.use(
      http.post(apiUrl("/api/v1/mentoring/requests/{request_id}/reject"), async ({ request }) => {
        const body = (await request.json()) as { reason: string };
        reasons.push(body);
        return HttpResponse.json(
          makeRequest({ ...REQUEST, status: "REJECTED", reject_reason: body.reason, rejected_at: NOW.toISOString() }),
        );
      }),
    );
    await renderRoute("/mentor/requests/r1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "반려" }));
    const dialog = await screen.findByRole("dialog", { name: "이 신청을 반려할까요?" });
    expect(within(dialog).getByText("0 / 300")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "반려하기" }));
    expect(await within(dialog).findByText("반려 사유를 적어 주세요.")).toBeInTheDocument();

    await user.type(within(dialog).getByRole("textbox", { name: /반려 사유/ }), "주말 오전으로 다시 신청해 주세요");
    await user.click(within(dialog).getByRole("button", { name: "반려하기" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(reasons).toEqual([{ reason: "주말 오전으로 다시 신청해 주세요" }]);
    const result = await screen.findByRole("region", { name: "처리 결과" });
    expect(within(result).getByText("반려한 신청이에요")).toBeInTheDocument();
    expect(within(result).getByText("주말 오전으로 다시 신청해 주세요")).toBeInTheDocument();
  });

  it("취소된 신청은 처리 결과에 사유와 주체를 보여 주고, 그 상대와의 방이 있으면 채팅으로 간다", async () => {
    mockDetail(
      makeRequest({
        status: "CANCELED",
        cancel_reason: "개인 일정으로 참석이 어려워요",
        canceled_by: "REQUESTER",
        canceled_at: "2026-11-18T12:40:00Z",
      }),
    );
    mockChat([makeThread({ id: "th1", mentor_id: "m1", student_id: "st12", kind: "DIRECT" })]);
    await renderRoute("/mentor/requests/r1");
    const result = await screen.findByRole("region", { name: "처리 결과" });
    expect(within(result).getByText("취소된 신청이에요")).toBeInTheDocument();
    expect(within(result).getByText("개인 일정으로 참석이 어려워요")).toBeInTheDocument();
    expect(within(result).getByText("11/18 21:40 가수강 취소")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /가수강과의 채팅에서 먼저 물어보기/ })).toHaveAttribute(
      "href",
      "/mentoring/chat/th1",
    );
    expect(screen.queryByRole("button", { name: "이 일시로 승인" })).not.toBeInTheDocument();
  });

  it("볼 수 없는 신청이면 안내한다 (404)", async () => {
    server.use(
      http.get(apiUrl("/api/v1/mentoring/requests/{request_id}"), () =>
        HttpResponse.json(errorBody("request_not_found"), { status: 404 }),
      ),
    );
    await renderRoute("/mentor/requests/zz");
    expect(await screen.findByRole("heading", { name: "신청을 찾을 수 없어요" })).toBeInTheDocument();
  });
});
