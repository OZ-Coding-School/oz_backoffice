import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { endSession, setAccessToken, useSession } from "@/api/session";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { makeMe, makeSignup, mockLogin, mockSignedIn, resetAuth } from "./test-utils";

beforeEach(() => resetAuth());

async function fillAndSubmit(email = "student@gmail.com", password = "secret1!") {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("이메일"), email);
  await user.type(screen.getByLabelText("비밀번호"), password);
  await user.click(screen.getByRole("button", { name: "로그인" }));
  return user;
}

describe("라우트 가드", () => {
  it("로그인하지 않고 홈에 오면 돌아갈 경로를 들고 로그인 화면으로 간다", async () => {
    const { router } = await renderRoute("/");
    expect(await screen.findByRole("heading", { name: "로그인" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
    expect(router.state.location.search).toEqual({ redirect: "/" });
  });

  it("새로 열어도 refresh 쿠키로 세션을 되살린다", async () => {
    mockSignedIn(makeMe());
    await renderRoute("/");
    expect(await screen.findByRole("heading", { name: "안녕하세요, 가수강님" })).toBeInTheDocument();
    expect((await screen.findAllByText("수강생 · 초격차 백엔드 12기")).length).toBeGreaterThan(0);
  });

  it("운영진이 회원 홈에 오면 운영진 홈으로 보낸다", async () => {
    mockSignedIn(
      makeMe({
        name: "김오즈",
        account_type: "STAFF",
        roles: [{ role: "SUPER_ADMIN", scope_type: "GLOBAL", scope_id: null, expires_at: null }],
      }),
    );
    const { router } = await renderRoute("/");
    expect(await screen.findByText("최고 관리자")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/admin");
  });

  it("이미 로그인했으면 로그인 화면 대신 홈으로 간다", async () => {
    mockSignedIn(makeMe());
    const { router } = await renderRoute("/login");
    await screen.findByRole("heading", { name: "안녕하세요, 가수강님" });
    expect(router.state.location.pathname).toBe("/");
  });
});

describe("로그인", () => {
  it("성공하면 돌아갈 경로로 간다", async () => {
    mockLogin(makeMe());
    const { router } = await renderRoute("/login?redirect=%2F");
    await fillAndSubmit();
    expect(await screen.findByRole("heading", { name: "안녕하세요, 가수강님" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });

  it("다른 사이트나 다른 계정 영역으로는 보내지 않는다", async () => {
    mockLogin(makeMe());
    const { router } = await renderRoute("/login?redirect=%2Fadmin");
    await fillAndSubmit();
    await screen.findByRole("heading", { name: "안녕하세요, 가수강님" });
    expect(router.state.location.pathname).toBe("/");
  });

  it("이메일·비밀번호가 틀리면 칸을 지목하지 않고 알리고 비밀번호를 비운다", async () => {
    server.use(
      http.post(apiUrl("/api/v1/auth/login"), () =>
        HttpResponse.json(errorBody("invalid_credentials"), { status: 401 }),
      ),
    );
    await renderRoute("/login");
    await fillAndSubmit();
    expect(await screen.findByRole("alert")).toHaveTextContent("이메일 또는 비밀번호가 올바르지 않아요");
    expect(screen.getByLabelText("비밀번호")).toHaveValue("");
    expect(screen.getByLabelText("이메일")).not.toBeInvalid();
  });

  it("잠기면 다시 시도할 시각을 보여 주고 버튼과 비밀번호 칸을 막는다", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-11-17T05:17:00Z") });
    server.use(
      http.post(apiUrl("/api/v1/auth/login"), () =>
        HttpResponse.json(errorBody("login_locked"), { status: 429, headers: { "Retry-After": "900" } }),
      ),
    );
    await renderRoute("/login");
    await fillAndSubmit();
    expect(await screen.findByRole("alert")).toHaveTextContent("14:32부터 다시 시도할 수 있어요");
    expect(screen.getByRole("button", { name: "14:32 이후 다시 시도" })).toBeDisabled();
    expect(screen.getByLabelText("비밀번호")).toBeDisabled();
    vi.useRealTimers();
  });

  it("세션이 탈취로 판정돼 끝났으면 폼 위에 안내한다", async () => {
    setAccessToken("t", new Date(Date.now() + 60_000).toISOString());
    endSession("refresh_token_reused", { broadcast: false });
    await renderRoute("/login");
    expect(await screen.findByRole("alert")).toHaveTextContent("보안을 위해 로그아웃됐어요");
  });

  it("처음 방문(쿠키 없음)은 안내하지 않는다", async () => {
    await renderRoute("/login");
    await screen.findByRole("heading", { name: "로그인" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("비밀번호 재설정 후 돌아오면 이메일을 채워 둔다", async () => {
    await renderRoute("/login?email=student%40gmail.com");
    expect(await screen.findByLabelText("이메일")).toHaveValue("student@gmail.com");
  });
});

describe("가입 상태 모달", () => {
  it("승인 대기면 신청 내용을 보여 주고 확인하면 로그아웃한다", async () => {
    mockLogin(makeMe({ approval_status: "PENDING", approved_at: null, roles: [] }));
    server.use(http.get(apiUrl("/api/v1/me/member-signup"), () => HttpResponse.json(makeSignup())));
    await renderRoute("/login");
    const user = await fillAndSubmit();
    const dialog = await screen.findByRole("dialog", { name: "가입 승인을 기다리고 있어요" });
    expect(await within(dialog).findByText("백엔드 12기")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "확인" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(useSession.getState().accessToken).toBeNull();
  });

  it("반려되면 사유를 보여 주고 멘토로 다시 신청해 바로 승인되면 홈으로 간다", async () => {
    mockLogin(makeMe({ approval_status: "REJECTED", approved_at: null, roles: [] }));
    server.use(
      http.get(apiUrl("/api/v1/me/member-signup"), () =>
        HttpResponse.json(makeSignup({ status: "REJECTED", reject_reason: "명단에 없어요." })),
      ),
    );
    const bodies: unknown[] = [];
    server.use(
      http.post(apiUrl("/api/v1/me/member-signup"), async ({ request }) => {
        bodies.push(await request.json());
        server.use(
          http.get(apiUrl("/api/v1/me"), () =>
            HttpResponse.json(
              makeMe({ roles: [{ role: "MENTOR", scope_type: "GLOBAL", scope_id: null, expires_at: null }] }),
            ),
          ),
        );
        return HttpResponse.json({
          user_id: "u1",
          name: "가수강",
          email: "student@gmail.com",
          phone_number: null,
          approval_status: "APPROVED",
          signup: makeSignup({ signup_type: "MENTOR", status: "APPROVED" }),
        });
      }),
    );
    const { router } = await renderRoute("/login");
    const user = await fillAndSubmit();
    const dialog = await screen.findByRole("dialog", { name: "가입이 반려됐어요" });
    expect(await within(dialog).findByText("명단에 없어요.")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("radio", { name: "멘토" }));
    await user.type(within(dialog).getByLabelText("닉네임 (선택)"), "오즈멘토");
    await user.click(within(dialog).getByRole("radio", { name: "닉네임" }));
    await user.click(within(dialog).getByRole("button", { name: "다시 신청하기" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(bodies).toEqual([{ signup_type: "MENTOR", nickname: "오즈멘토", display_name_preference: "NICKNAME" }]);
    expect(await screen.findByText("가입이 승인됐어요")).toBeInTheDocument();
  });

  it("수강생 재신청은 기수를 골라야 한다", async () => {
    mockLogin(makeMe({ approval_status: "REJECTED", approved_at: null, roles: [] }));
    server.use(
      http.get(apiUrl("/api/v1/me/member-signup"), () =>
        HttpResponse.json(makeSignup({ status: "REJECTED", requested_cohort_id: null, reject_reason: "기수 확인" })),
      ),
    );
    await renderRoute("/login");
    const user = await fillAndSubmit();
    const dialog = await screen.findByRole("dialog", { name: "가입이 반려됐어요" });
    await user.click(within(dialog).getByRole("button", { name: "다시 신청하기" }));
    expect(await within(dialog).findByText("신청 기수를 골라 주세요.")).toBeInTheDocument();
  });
});
