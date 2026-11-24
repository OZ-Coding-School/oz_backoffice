import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { setThemePreference } from "@/lib/theme";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

beforeEach(() => {
  resetAuth();
  setThemePreference("light");
});

describe("회원 공통 틀 (F27)", () => {
  it("수강생은 홈 메뉴·인사말과 할 일 요약을 보고, 상단 막대에는 기수를 표시하지 않는다", async () => {
    mockSignedIn(makeMe());
    await renderRoute("/");
    expect(await screen.findByRole("heading", { name: "안녕하세요, 가수강님" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "할 일 요약" })).toBeInTheDocument();
    expect((await screen.findAllByText("수강생 · 초격차 백엔드 12기")).length).toBeGreaterThan(0);
    expect(within(screen.getByRole("banner")).queryByText(/초격차 백엔드/)).not.toBeInTheDocument();
    const menus = screen.getAllByRole("navigation", { name: "메뉴" });
    for (const menu of menus) {
      expect(within(menu).getByRole("link", { name: "홈" })).toHaveAttribute("aria-current", "page");
      // 만든 메뉴만: 홈·멘토링 신청(F31, 기수 설정을 받은 뒤)·신청 내역·진행 기록(F33)·채팅(F40)·시간 내역(F38)·내 정보(F37)
      await waitFor(() => expect(within(menu).getAllByRole("link")).toHaveLength(7));
    }
    const bottom = screen.getByRole("navigation", { name: "하단 메뉴" }); // 메뉴 2개 이상
    // 메뉴 6개: 4개 + 더보기 (F36)
    await waitFor(() => expect(within(bottom).getAllByRole("link")).toHaveLength(4));
    await userEvent.setup().click(within(bottom).getByRole("button", { name: "더보기" }));
    const sheet = await screen.findByRole("dialog", { name: "더보기" });
    expect(within(sheet).getByRole("link", { name: "시간 지급·차감 내역" })).toBeInTheDocument();
    expect(within(sheet).getByRole("link", { name: "내 정보" })).toBeInTheDocument();
  });

  it("멘토는 기수를 보지 않고 수강 등록도 부르지 않는다", async () => {
    const requested = vi.fn<() => void>();
    server.use(http.get(apiUrl("/api/v1/me/enrollments"), () => (requested(), HttpResponse.json([]))));
    mockSignedIn(makeMe({ name: "김멘토", account_type: "MENTOR", is_super_admin: false }));
    await renderRoute("/");
    expect(await screen.findByRole("heading", { name: "안녕하세요, 김멘토님" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "할 일 요약" })).toBeInTheDocument(); // 멘토 홈 (F57)
    expect(screen.getAllByText("멘토").length).toBeGreaterThan(0);
    expect(requested).not.toHaveBeenCalled();
  });

  it("테마 버튼은 라이트↔다크를 바꾼다", async () => {
    mockSignedIn(makeMe());
    const user = userEvent.setup();
    await renderRoute("/");
    await user.click(await screen.findByRole("button", { name: "다크 모드로 바꾸기" }));
    expect(document.documentElement).toHaveClass("dark");
    await user.click(screen.getByRole("button", { name: "라이트 모드로 바꾸기" }));
    expect(document.documentElement).not.toHaveClass("dark");
  });

  it("사용자 메뉴에서 로그아웃하면 로그인 화면으로 간다", async () => {
    mockSignedIn(makeMe());
    const user = userEvent.setup();
    const { router } = await renderRoute("/");
    await user.click(await screen.findByRole("button", { name: "사용자 메뉴" }));
    const menu = await screen.findByRole("menu");
    expect(within(menu).getByText("수강생 · 초격차 백엔드 12기")).toBeInTheDocument();
    await user.click(within(menu).getByRole("menuitem", { name: "로그아웃" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });
});
