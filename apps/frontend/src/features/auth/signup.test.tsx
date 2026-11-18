import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { resetAuth } from "./test-utils";

type User = ReturnType<typeof userEvent.setup>;
const calls: Record<string, unknown[]> = {};

function mockSignupApi({ approval = "APPROVED" }: { approval?: "APPROVED" | "PENDING" } = {}) {
  for (const key of Object.keys(calls)) delete calls[key];
  const record = (key: string, body: unknown) => (calls[key] ??= []).push(body);
  server.use(
    http.post(apiUrl("/api/v1/auth/signup/email-code"), async ({ request }) => {
      record("email-code", await request.json());
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(apiUrl("/api/v1/auth/signup/email-code/verify"), async ({ request }) => {
      const body = (await request.json()) as { code: string };
      record("email-verify", body);
      if (body.code !== "123456") return HttpResponse.json(errorBody("invalid_verification_code"), { status: 422 });
      return HttpResponse.json({ signup_token: "signup-token", expires_in: 1800 });
    }),
    http.post(apiUrl("/api/v1/auth/signup/phone-code"), async ({ request }) => {
      record("phone-code", await request.json());
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(apiUrl("/api/v1/auth/signup/phone-code/verify"), async ({ request }) => {
      record("phone-verify", await request.json());
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(apiUrl("/api/v1/auth/signup"), async ({ request }) => {
      record("signup", await request.json());
      return HttpResponse.json(
        { user_id: "u1", signup_id: "s1", signup_type: "STUDENT", approval_status: approval },
        { status: 201 },
      );
    }),
  );
}

beforeEach(() => {
  resetAuth();
  window.sessionStorage.clear();
  mockSignupApi();
});

async function toPhoneStep(user: User, type: "수강생" | "멘토" = "수강생") {
  await user.click(await screen.findByRole("radio", { name: new RegExp(type) }));
  await user.click(screen.getByRole("button", { name: "다음" }));
  await user.type(await screen.findByLabelText("이메일"), "student@gmail.com");
  await user.click(screen.getByRole("button", { name: "인증코드 받기" }));
  await user.type(await screen.findByLabelText("인증코드"), "123456");
  await user.click(screen.getByRole("button", { name: "확인" }));
  await screen.findByLabelText("휴대폰 번호");
}

async function verifyPhone(user: User) {
  await user.type(screen.getByLabelText("휴대폰 번호"), "01012345678");
  expect(screen.getByLabelText("휴대폰 번호")).toHaveValue("010-1234-5678");
  await user.click(screen.getByRole("button", { name: "인증코드 받기" }));
  await user.type(await screen.findByLabelText("인증코드"), "654321");
  await user.click(screen.getByRole("button", { name: "확인" }));
  await screen.findByRole("heading", { name: "가입 정보" });
}

describe("회원가입", () => {
  it("수강생은 유형 → 이메일 → 휴대폰 → 가입 정보를 거쳐 바로 승인되면 로그인으로 안내한다", async () => {
    const user = userEvent.setup();
    const { router } = await renderRoute("/signup");
    await toPhoneStep(user);
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("휴대폰 인증");
    await verifyPhone(user);

    await user.type(screen.getByLabelText("이름"), "가수강");
    await user.click(screen.getByRole("combobox", { name: "신청 기수" }));
    await user.click(await screen.findByRole("option", { name: /백엔드 12기/ }));
    await user.type(screen.getByLabelText("비밀번호", { selector: "input" }), "secret12!");
    await user.type(screen.getByLabelText("비밀번호 확인"), "secret12!");
    await user.click(screen.getByRole("button", { name: "가입 신청" }));

    expect(await screen.findByRole("heading", { name: "가입이 완료됐어요" })).toBeInTheDocument();
    expect(calls["phone-code"]).toEqual([{ signup_token: "signup-token", phone_number: "01012345678" }]);
    expect(calls.signup).toEqual([
      {
        signup_token: "signup-token",
        signup_type: "STUDENT",
        name: "가수강",
        password: "secret12!",
        cohort_id: "c12",
      },
    ]);
    expect(window.sessionStorage.getItem("oz-signup")).toBeNull();

    await user.click(screen.getByRole("link", { name: "로그인하기" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(await screen.findByLabelText("이메일")).toHaveValue("student@gmail.com");
  });

  it("멘토는 닉네임과 보일 이름을 받고, 승인 대기면 확인 안내를 보여 준다", async () => {
    mockSignupApi({ approval: "PENDING" });
    const user = userEvent.setup();
    await renderRoute("/signup");
    await toPhoneStep(user, "멘토");
    await verifyPhone(user);
    await user.type(screen.getByLabelText("이름 (실명)"), "김멘토");
    await user.type(screen.getByLabelText("닉네임 (선택)"), "멘토K");
    await user.click(screen.getByRole("radio", { name: "닉네임 (멘토K)" }));
    await user.type(screen.getByLabelText("비밀번호", { selector: "input" }), "secret12!");
    await user.type(screen.getByLabelText("비밀번호 확인"), "secret12!");
    await user.click(screen.getByRole("button", { name: "가입 신청" }));

    expect(await screen.findByRole("heading", { name: "가입 신청을 받았어요" })).toBeInTheDocument();
    expect(screen.getByText(/계약 정보에서 일치하는 정보를 찾지 못해/)).toBeInTheDocument();
    expect(calls.signup).toEqual([
      expect.objectContaining({ signup_type: "MENTOR", nickname: "멘토K", display_name_preference: "NICKNAME" }),
    ]);
  });

  it("새로고침해도 진행 중인 단계로 돌아온다", async () => {
    const user = userEvent.setup();
    const first = await renderRoute("/signup");
    await toPhoneStep(user);
    first.unmount();
    await renderRoute("/signup");
    expect(await screen.findByLabelText("휴대폰 번호")).toBeInTheDocument();
  });

  it("가입 토큰이 만료되면 처음부터 다시 하게 한다", async () => {
    server.use(
      http.post(apiUrl("/api/v1/auth/signup/phone-code"), () =>
        HttpResponse.json(errorBody("signup_session_expired"), { status: 422 }),
      ),
    );
    const user = userEvent.setup();
    await renderRoute("/signup");
    await toPhoneStep(user);
    await user.type(screen.getByLabelText("휴대폰 번호"), "01012345678");
    await user.click(screen.getByRole("button", { name: "인증코드 받기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("인증 시간이 지났어요");
    await user.click(screen.getByRole("button", { name: "처음부터 다시" }));
    expect(await screen.findByRole("heading", { name: "회원가입" })).toBeInTheDocument();
  });

  it("이미 가입된 이메일은 칸에 알리고 로그인·재설정으로 안내한다", async () => {
    server.use(
      http.post(apiUrl("/api/v1/auth/signup/email-code"), () =>
        HttpResponse.json(errorBody("email_already_registered"), { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    await renderRoute("/signup");
    await user.click(await screen.findByRole("button", { name: "다음" }));
    await user.type(await screen.findByLabelText("이메일"), "student@gmail.com");
    await user.click(screen.getByRole("button", { name: "인증코드 받기" }));
    expect(await screen.findByText("이미 가입된 이메일이에요.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "로그인하기" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "비밀번호 재설정" })).toBeInTheDocument();
  });

  it("요청이 너무 많으면 다시 시도할 시각을 알리고 버튼을 막는다", async () => {
    server.use(
      http.post(apiUrl("/api/v1/auth/signup/email-code"), () =>
        HttpResponse.json(errorBody("rate_limited"), { status: 429, headers: { "Retry-After": "600" } }),
      ),
    );
    const user = userEvent.setup();
    await renderRoute("/signup");
    await user.click(await screen.findByRole("button", { name: "다음" }));
    await user.type(await screen.findByLabelText("이메일"), "student@gmail.com");
    await user.click(screen.getByRole("button", { name: "인증코드 받기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/\d\d:\d\d 이후에 다시 시도해 주세요/);
    expect(screen.getByRole("button", { name: "인증코드 받기" })).toBeDisabled();
  });

  it("인증코드가 틀리면 코드 칸에 알린다", async () => {
    const user = userEvent.setup();
    await renderRoute("/signup");
    await user.click(await screen.findByRole("button", { name: "다음" }));
    await user.type(await screen.findByLabelText("이메일"), "student@gmail.com");
    await user.click(screen.getByRole("button", { name: "인증코드 받기" }));
    await user.type(await screen.findByLabelText("인증코드"), "000000");
    await user.click(screen.getByRole("button", { name: "확인" }));
    expect(await screen.findByText(/인증코드가 맞지 않아요. 5번 틀리면/)).toBeInTheDocument();
  });
});
