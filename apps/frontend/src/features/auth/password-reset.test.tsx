import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { resetAuth } from "./test-utils";

beforeEach(() => {
  resetAuth();
  server.use(http.post(apiUrl("/api/v1/auth/password-reset/code"), () => new HttpResponse(null, { status: 204 })));
});

async function toCodeStep() {
  const user = userEvent.setup();
  await renderRoute("/password-reset");
  await user.type(await screen.findByLabelText("이메일"), "student@gmail.com");
  await user.click(screen.getByRole("button", { name: "인증코드 받기" }));
  await screen.findByRole("heading", { name: "새 비밀번호 만들기" });
  return user;
}

async function fillCode(user: ReturnType<typeof userEvent.setup>, code = "123456", password = "newpass1!") {
  await user.type(screen.getByLabelText("인증코드"), code);
  await user.type(screen.getByLabelText("새 비밀번호"), password);
  await user.type(screen.getByLabelText("새 비밀번호 확인"), password);
}

describe("비밀번호 재설정", () => {
  it("코드를 받으면 보낸 이메일과 재발송 대기 시간을 보여 준다", async () => {
    await toCodeStep();
    expect(screen.getByText(/student@gmail.com으로 코드를 보냈어요/)).toBeInTheDocument();
    expect(screen.getByText(/코드 다시 받기는 \d:\d\d 뒤에 할 수 있어요/)).toBeInTheDocument();
  });

  it("비밀번호 규칙을 입력하는 동안 체크로 보여 주고, 모두 맞아야 바꿀 수 있다", async () => {
    const user = await toCodeStep();
    await user.type(screen.getByLabelText("인증코드"), "123456");
    await user.type(screen.getByLabelText("새 비밀번호"), "abcdefgh1");
    const rules = screen.getByRole("list", { name: "비밀번호 규칙" });
    expect(rules).toHaveTextContent("8~64자 (충족)");
    expect(rules).toHaveTextContent("특수문자 포함 (미충족)");
    expect(screen.getByRole("button", { name: "비밀번호 변경" })).toBeDisabled();
  });

  it("코드가 틀리면 코드 칸에만 오류를 표시한다", async () => {
    server.use(
      http.post(apiUrl("/api/v1/auth/password-reset"), () =>
        HttpResponse.json(errorBody("invalid_verification_code"), { status: 422 }),
      ),
    );
    const user = await toCodeStep();
    await fillCode(user);
    await user.click(screen.getByRole("button", { name: "비밀번호 변경" }));
    expect(await screen.findByText("인증코드가 맞지 않아요.")).toBeInTheDocument();
    expect(screen.getByLabelText("인증코드")).toBeInvalid();
  });

  it("바꾸면 로그인 화면으로 돌아와 이메일을 채우고 알린다", async () => {
    let body: unknown;
    server.use(
      http.post(apiUrl("/api/v1/auth/password-reset"), async ({ request }) => {
        body = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = await toCodeStep();
    await fillCode(user);
    await user.click(screen.getByRole("button", { name: "비밀번호 변경" }));
    expect(await screen.findByLabelText("이메일")).toHaveValue("student@gmail.com");
    expect(await screen.findByText("비밀번호를 바꿨어요")).toBeInTheDocument();
    expect(body).toEqual({ email: "student@gmail.com", code: "123456", new_password: "newpass1!" });
  });

  it("요청이 너무 많으면 다시 시도할 시각을 알린다", async () => {
    server.use(
      http.post(apiUrl("/api/v1/auth/password-reset/code"), () =>
        HttpResponse.json(errorBody("rate_limited"), { status: 429, headers: { "Retry-After": "600" } }),
      ),
    );
    const user = userEvent.setup();
    await renderRoute("/password-reset");
    await user.type(await screen.findByLabelText("이메일"), "student@gmail.com");
    await user.click(screen.getByRole("button", { name: "인증코드 받기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/\d\d:\d\d부터 다시 시도할 수 있어요/);
  });
});
