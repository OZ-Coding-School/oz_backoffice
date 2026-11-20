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
  it("수강생은 홈 메뉴·인사말과 빈 상태를 보고, 상단 막대에는 기수를 표시하지 않는다", async () => {
    mockSignedIn(makeMe());
    await renderRoute("/");
    expect(await screen.findByRole("heading", { name: "안녕하세요, 가수강님" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "할 일 요약이 곧 여기에 모여요" })).toBeInTheDocument();
    expect((await screen.findAllByText("수강생 · 초격차 백엔드 12기")).length).toBeGreaterThan(0);
    expect(within(screen.getByRole("banner")).queryByText(/초격차 백엔드/)).not.toBeInTheDocument();
    const menus = screen.getAllByRole("navigation", { name: "메뉴" });
    for (const menu of menus) {
      expect(within(menu).getByRole("link", { name: "홈" })).toHaveAttribute("aria-current", "page");
      // 만든 메뉴만: 홈·멘토링 신청(F31, 기수 설정을 받은 뒤)·신청 내역·진행 기록(F33)
      await waitFor(() => expect(within(menu).getAllByRole("link")).toHaveLength(4));
    }
    expect(screen.getByRole("navigation", { name: "하단 메뉴" })).toBeInTheDocument(); // 메뉴 2개 이상
  });

  it("멘토는 기수를 보지 않고 수강 등록도 부르지 않는다", async () => {
    const requested = vi.fn<() => void>();
    server.use(http.get(apiUrl("/api/v1/me/enrollments"), () => (requested(), HttpResponse.json([]))));
    mockSignedIn(makeMe({ name: "김멘토", account_type: "MENTOR", roles: [] }));
    await renderRoute("/");
    expect(await screen.findByRole("heading", { name: "안녕하세요, 김멘토님" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "처리할 신청·오늘 세션이 곧 여기에 모여요" })).toBeInTheDocument();
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
