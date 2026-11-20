import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { LEDGER, makeAccount, mockBalances, tx } from "./test-utils";

const TEAM = makeAccount({
  id: "a2",
  owner_type: "TEAM",
  owner_id: "t3",
  owner_name: "3팀 알파",
  held_minutes: 0,
  used_minutes: 180,
  remaining_minutes: 300,
});

beforeEach(() => {
  resetAuth();
  mockSignedIn(makeMe());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("시간 지급·차감 내역 (F38)", () => {
  it("1:1 계좌 내역을 먼저 보여 주고, 계좌 카드를 누르면 그 계좌 내역으로 바꾼다", async () => {
    const seen = mockBalances([TEAM, makeAccount()], {
      a1: LEDGER,
      a2: [tx("u1", "STAFF_GRANT", 480, 480, "팀 기본 지급", "2026-11-01T00:00:00Z")],
    });
    const user = userEvent.setup();
    await renderRoute("/mentoring/balances");

    const accounts = await screen.findByRole("navigation", { name: "계좌" });
    const one = within(accounts).getByRole("link", { name: /1:1 계좌/ });
    expect(one).toHaveAttribute("aria-current", "true");
    expect(within(one).getByText("3시간 30분")).toBeInTheDocument();

    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(
      rows.map((r) =>
        within(r)
          .getAllByRole("cell")
          .map((c) => c.textContent),
      ),
    ).toEqual([
      ["11/16 10:02", "차감 예정", "−60분", "3시간 30분", "멘토링 신청"],
      ["11/15 11:20", "추가 차감", "−30분", "4시간 30분", "실제 진행 시간이 신청보다 김"],
      ["11/14 22:30", "차감", "— · 확정 1시간", "5시간", "멘토링 승인"],
      ["11/14 21:10", "차감 예정", "−60분", "5시간", "멘토링 신청"],
      ["11/10 11:00", "지급", "+120분", "6시간", "11월 추가 멘토링 시간"],
      ["11/01 00:00", "지급", "+240분", "4시간", "기본 지급"],
    ]);

    await user.click(within(accounts).getByRole("link", { name: /3팀 알파 계좌/ }));
    expect(await screen.findByRole("cell", { name: "팀 기본 지급" })).toBeInTheDocument();
    await waitFor(() => expect(seen.at(-1)?.account).toBe("a2"));
  });

  it("만료 계좌는 배지와 함께 뒤에 둔다", async () => {
    mockBalances([makeAccount({ id: "a0", is_expired: true }), makeAccount()], { a1: LEDGER, a0: [] });
    await renderRoute("/mentoring/balances");
    const links = within(await screen.findByRole("navigation", { name: "계좌" })).getAllByRole("link");
    expect(links.map((l) => l.getAttribute("href"))).toEqual([
      "/mentoring/balances?account=a1",
      "/mentoring/balances?account=a0",
    ]);
    expect(within(links[1]!).getByText("만료")).toBeInTheDocument();
  });

  it("계좌가 없으면 빈 상태, 내역이 없으면 내역 빈 상태", async () => {
    mockBalances([], {});
    await renderRoute("/mentoring/balances");
    expect(await screen.findByRole("heading", { name: "아직 받은 멘토링 시간이 없어요" })).toBeInTheDocument();
  });

  it("내역이 비면 알려 준다", async () => {
    mockBalances([makeAccount()], { a1: [] });
    await renderRoute("/mentoring/balances");
    expect(await screen.findByRole("heading", { name: "아직 내역이 없어요" })).toBeInTheDocument();
  });

  it("목록 끝이 보이면 이전 20개를 before 커서로 이어 붙인다", async () => {
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
    const many = Array.from({ length: 25 }, (_, i) =>
      tx(`t${i}`, "STAFF_GRANT", 60, 60 * (25 - i), `지급 ${i + 1}`, "2026-11-01T00:00:00Z"),
    );
    const seen = mockBalances([makeAccount()], { a1: many });
    await renderRoute("/mentoring/balances");
    expect(await screen.findByRole("cell", { name: "지급 20" })).toBeInTheDocument();
    expect(screen.queryByRole("cell", { name: "지급 21" })).not.toBeInTheDocument();
    observers.at(-1)?.([{ isIntersecting: true }]);
    expect(await screen.findByRole("cell", { name: "지급 25" })).toBeInTheDocument();
    expect(new Set(seen.map((s) => s.before))).toEqual(new Set([null, "t19"]));
  });

  it("불러오지 못하면 다시 시도할 수 있다", async () => {
    server.use(http.get(apiUrl("/api/v1/me/balances"), () => HttpResponse.json(errorBody("x"), { status: 500 })));
    await renderRoute("/mentoring/balances");
    expect(await screen.findByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });
});
