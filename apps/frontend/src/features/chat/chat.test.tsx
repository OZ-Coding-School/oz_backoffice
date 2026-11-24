import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { renderRoute } from "@/test/render";

import { makeMessage, makeThread, mockChat } from "./test-utils";

const TEAM = makeThread({
  id: "th2",
  kind: "TEAM",
  student_id: null,
  student_name: null,
  team_id: "t3",
  team_label: "3팀 알파",
  mentor_display_name: "이멘토",
  last_message: makeMessage({ thread_id: "th2", sender_name: "나수강", body: "API 명세 링크 올려둘게요!" }),
  unread_count: 1,
});

const HISTORY = [
  makeMessage({
    sender_kind: "SYSTEM",
    sender_id: null,
    sender_name: null,
    body: "[멘토링 신청] 주제: 포트폴리오 리뷰",
  }),
  makeMessage({ body: "README 링크 미리 공유드려요!" }),
  makeMessage({ sender_kind: "MENTOR", sender_id: "mu1", sender_name: "멘토K", body: "확인했어요." }),
  makeMessage({ body: null, is_deleted: true }),
];

beforeEach(() => {
  resetAuth();
  mockSignedIn(makeMe());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("채팅 (F40·A74)", () => {
  it("방 목록은 상대·미리보기·안 읽음을 보여 주고, 방을 고르기 전에는 안내한다", async () => {
    mockChat([makeThread({ last_message: HISTORY[2], unread_count: 0 }), TEAM]);
    await renderRoute("/mentoring/chat");
    const list = await screen.findByRole("region", { name: "채팅" });
    expect(within(list).getByRole("link", { name: "멘토K" })).toHaveAttribute("href", "/mentoring/chat/th1");
    const team = within(list).getByRole("link", { name: "3팀 알파 · 이멘토 · 안 읽음 1" });
    expect(within(team).getByText("나수강: API 명세 링크 올려둘게요!")).toBeInTheDocument();
    expect(within(list).getByText("확인했어요.")).toBeInTheDocument();
    expect(screen.getByText("대화를 골라 주세요")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /새 대화/ })).not.toBeInTheDocument();
  });

  it("방이 없으면 신청하면 대화할 수 있다고 알려 준다", async () => {
    mockChat([]);
    await renderRoute("/mentoring/chat");
    expect(await screen.findByText("아직 대화가 없어요")).toBeInTheDocument();
    expect(screen.getByText("멘토링을 신청하면 멘토와 대화할 수 있어요")).toBeInTheDocument();
  });

  it("대화: 오래된 것부터 보여 주고, 안 읽음이 있으면 마지막 메시지까지 읽음 처리한다", async () => {
    const calls = mockChat([makeThread({ unread_count: 1 })], { th1: HISTORY });
    await renderRoute("/mentoring/chat/th1");
    const convo = await screen.findByRole("region", { name: "멘토K" });
    const items = within(convo)
      .getAllByRole("listitem")
      .map((li) => li.textContent);
    expect(items[0]).toContain("[멘토링 신청] 주제: 포트폴리오 리뷰");
    expect(items[1]).toContain("나 · ");
    expect(items[2]).toContain("멘토K · ");
    expect(items[3]).toContain("삭제된 메시지입니다.");
    await waitFor(() => expect(calls.read).toEqual([HISTORY[3]!.id]));
  });

  it("Enter로 보내고 Shift+Enter는 줄을 바꾼다", async () => {
    const calls = mockChat([makeThread()], { th1: HISTORY.slice(0, 2) });
    const user = userEvent.setup();
    await renderRoute("/mentoring/chat/th1");
    const box = await screen.findByRole("textbox", { name: "메시지" });
    await user.type(box, "첫 줄{Shift>}{Enter}{/Shift}둘째 줄");
    expect(calls.sent).toEqual([]);
    expect(screen.getByText("8 / 2,000")).toBeInTheDocument();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(calls.sent).toEqual(["첫 줄\n둘째 줄"]));
    expect(box).toHaveValue("");
    expect(await screen.findByText(/둘째 줄/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "보내기" })).toBeDisabled();
  });

  it("본인 메시지는 확인 창을 거쳐 삭제한다", async () => {
    const calls = mockChat([makeThread()], { th1: HISTORY.slice(0, 3) });
    const user = userEvent.setup();
    await renderRoute("/mentoring/chat/th1");
    const deletes = await screen.findAllByRole("button", { name: "메시지 삭제" });
    expect(deletes).toHaveLength(1); // 내 메시지만
    await user.click(deletes[0]!);
    const dialog = await screen.findByRole("dialog", { name: "메시지를 삭제할까요?" });
    expect(within(dialog).getByText("README 링크 미리 공유드려요!")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "삭제" }));
    await waitFor(() => expect(calls.deleted).toEqual([HISTORY[1]!.id]));
    expect(await screen.findByText("삭제된 메시지입니다.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "메시지 삭제" })).not.toBeInTheDocument();
  });

  it("위로 올리면 이전 메시지를 before 커서로 불러온다", async () => {
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
    const many = Array.from({ length: 55 }, (_, i) => makeMessage({ body: `과거 ${i + 1}` }));
    const calls = mockChat([makeThread()], { th1: many });
    await renderRoute("/mentoring/chat/th1");
    expect(await screen.findByText("과거 55")).toBeInTheDocument();
    expect(screen.queryByText("과거 5")).not.toBeInTheDocument();
    observers.at(-1)?.([{ isIntersecting: true }]);
    expect(await screen.findByText("과거 5")).toBeInTheDocument();
    expect(calls.before).toContain(many[5]!.id);
  });

  it("볼 수 없는 방은 찾을 수 없다고 알려 준다", async () => {
    mockChat([]);
    await renderRoute("/mentoring/chat/nope");
    expect(await screen.findByRole("heading", { name: "채팅방을 찾을 수 없어요" })).toBeInTheDocument();
  });

  it("멘토는 수강생·팀 이름과 1:1/팀으로 방을 본다", async () => {
    mockSignedIn(makeMe({ account_type: "MENTOR", name: "김멘토", is_super_admin: false }));
    mockChat([makeThread(), TEAM]);
    await renderRoute("/mentoring/chat");
    const list = await screen.findByRole("region", { name: "채팅" });
    const direct = within(list).getByRole("link", { name: "가수강" });
    expect(within(direct).getByText("1:1")).toBeInTheDocument();
    expect(within(list).getByRole("link", { name: "3팀 알파 · 안 읽음 1" })).toBeInTheDocument();
  });
});
