import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, pushableSse, resetAuth, sseResponse } from "@/features/auth/test-utils";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { makeMessage, makeThread, mockChat } from "./test-utils";

const frame = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

beforeEach(() => {
  resetAuth();
  mockSignedIn(makeMe());
});

afterEach(() => {
  vi.useRealTimers();
});

describe("채팅 실시간 수신 (A58·F41)", () => {
  it("받은 메시지를 열린 방에 붙이고, 삭제 알림은 '삭제된 메시지'로 바꾼다", async () => {
    const old = makeMessage({ sender_kind: "MENTOR", sender_id: "mu1", sender_name: "멘토K", body: "곧 지울 말" });
    mockChat([makeThread()], { th1: [old] });
    const incoming = makeMessage({
      sender_kind: "MENTOR",
      sender_id: "mu1",
      sender_name: "멘토K",
      body: "실시간 답변",
    });
    const sse = pushableSse();
    server.use(http.get(apiUrl("/api/v1/me/mentoring/chat/stream"), () => sse.respond()));
    await renderRoute("/mentoring/chat/th1");
    const convo = await screen.findByRole("region", { name: "멘토K" });
    expect(await within(convo).findByText("곧 지울 말")).toBeInTheDocument();
    act(() => {
      sse.push(frame("message", incoming));
      sse.push(frame("message_deleted", { ...old, body: null, is_deleted: true }));
    });
    expect(await within(convo).findByText("실시간 답변")).toBeInTheDocument();
    await waitFor(() => expect(within(convo).queryByText("곧 지울 말")).not.toBeInTheDocument());
    expect(within(convo).getByText("삭제된 메시지입니다.")).toBeInTheDocument();
  });

  it("메뉴의 채팅에 방별 안 읽음 합을 보여 주고, read 알림으로 줄인다", async () => {
    mockChat([makeThread({ unread_count: 2 }), makeThread({ id: "th2", mentor_id: "m2", unread_count: 3 })]);
    server.use(http.get(apiUrl("/api/v1/me/mentoring/chat/stream"), () => sseResponse(["event: ready\ndata: {}\n\n"])));
    await renderRoute("/");
    const sidebar = (await screen.findAllByRole("navigation", { name: "메뉴" }))[0]!;
    const chat = await within(sidebar).findByRole("link", { name: /채팅/ });
    await waitFor(() => expect(chat).toHaveTextContent("안 읽음 5"));
    const tabs = screen.getByRole("navigation", { name: "하단 메뉴" });
    expect(within(tabs).getByRole("button", { name: /더보기/ })).toHaveTextContent("안 읽음 5");
  });

  it("끊기면 다시 연결하고, 다시 연결되면 방 목록을 다시 조회한다", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let connections = 0;
    let listCalls = 0;
    mockChat([makeThread()]);
    server.use(
      http.get(apiUrl("/api/v1/me/mentoring/chat/threads"), () => {
        listCalls += 1;
        return HttpResponse.json({ items: [makeThread()], total: 1, limit: 50, offset: 0 });
      }),
      http.get(apiUrl("/api/v1/me/mentoring/chat/stream"), () => {
        connections += 1;
        // 첫 연결은 ready 뒤 바로 끊긴다
        if (connections === 1)
          return new HttpResponse("event: ready\ndata: {}\n\n", { headers: { "Content-Type": "text/event-stream" } });
        return sseResponse(["event: ready\ndata: {}\n\n"]);
      }),
    );
    await renderRoute("/mentoring/chat");
    await screen.findByRole("region", { name: "채팅" });
    await waitFor(() => expect(connections).toBe(1));
    const before = listCalls;
    await act(() => vi.advanceTimersByTimeAsync(3_000));
    await waitFor(() => expect(connections).toBe(2));
    await waitFor(() => expect(listCalls).toBeGreaterThan(before));
  });
});
