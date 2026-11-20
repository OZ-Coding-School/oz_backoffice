import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { PasswordChangeStatus } from "./api";
import { maskEmail, maskPhone } from "./mask";

const NONE: PasswordChangeStatus = { available: true, state: "NONE", expires_at: null };

/** 상태 조회는 current를, 링크 보내기는 SENT를 돌려준다 */
function mockPasswordChange(initial: PasswordChangeStatus = NONE) {
  const calls = { link: 0, change: [] as unknown[] };
  let current = initial;
  server.use(
    http.get(apiUrl("/api/v1/me/password-change"), () => HttpResponse.json(current)),
    http.post(apiUrl("/api/v1/me/password-change/link"), () => {
      calls.link += 1;
      current = { available: true, state: "SENT", expires_at: new Date(Date.now() + 30 * 60_000).toISOString() };
      return HttpResponse.json(current);
    }),
    http.post(apiUrl("/api/v1/me/password-change"), async ({ request }) => {
      calls.change.push(await request.json());
      current = NONE;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return {
    calls,
    verify: () => {
      current = { available: true, state: "VERIFIED", expires_at: new Date(Date.now() + 10 * 60_000).toISOString() };
    },
  };
}

beforeEach(() => {
  resetAuth();
  mockSignedIn(makeMe());
});

afterEach(() => {
  vi.useRealTimers();
});

describe("가리기", () => {
  it("휴대폰 가운데 4자리와 이메일 아이디를 가린다", () => {
    expect(maskPhone("01012345678")).toBe("010-****-5678");
    expect(maskPhone("010-1234-5678")).toBe("010-****-5678");
    expect(maskPhone(null)).toBeNull();
    expect(maskEmail("student@gmail.com")).toBe("st****@gmail.com");
    expect(maskEmail("a@b.com")).toBe("a****@b.com");
  });
});

describe("내 정보 (F37)", () => {
  it("계정·수강 정보를 보여 준다", async () => {
    mockPasswordChange();
    await renderRoute("/my/profile");
    expect(await screen.findByRole("heading", { name: "내 정보" })).toBeInTheDocument();
    const account = screen.getByRole("region", { name: "계정" });
    expect(within(account).getByText("가수강")).toBeInTheDocument();
    expect(within(account).getByText("승인됨")).toBeInTheDocument();
    expect(within(account).getByText("초격차 백엔드 12기 · 수강 중")).toBeInTheDocument();
    expect(within(account).getByText("student@gmail.com")).toBeInTheDocument();
    expect(within(account).getByText("010-****-5678")).toBeInTheDocument();
    expect(within(account).getByText("2026.10.01 ~ 2027.03.31")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "비밀번호 재설정" })).toBeInTheDocument();
  });

  it("비밀번호가 없는 계정에는 재설정 버튼이 없다", async () => {
    mockPasswordChange({ available: false, state: "NONE", expires_at: null });
    await renderRoute("/my/profile");
    expect(await screen.findByRole("region", { name: "계정" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "비밀번호 재설정" })).not.toBeInTheDocument();
  });

  it("링크를 보내고 5초마다 확인하다가, 인증되면 규칙·일치를 보여 주며 바꾼다 (A72)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const mock = mockPasswordChange();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await renderRoute("/my/profile");
    await user.click(await screen.findByRole("button", { name: "비밀번호 재설정" }));

    const dialog = await screen.findByRole("dialog", { name: "비밀번호 변경" });
    expect(await within(dialog).findByText("st****@gmail.com으로 인증 링크를 보냈어요")).toBeInTheDocument();
    expect(mock.calls.link).toBe(1);
    expect(within(dialog).getByLabelText("새 비밀번호")).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "변경 저장" })).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: /다시 보내기 \(\d+초\)/ })).toBeDisabled();

    mock.verify();
    await act(() => vi.advanceTimersByTimeAsync(5_000));
    expect(await within(dialog).findByText("이메일 인증이 완료되었습니다.")).toBeInTheDocument();
    const next = within(dialog).getByLabelText("새 비밀번호");
    expect(next).toBeEnabled();

    await user.type(next, "abc");
    expect(within(dialog).getByText("8~64자")).toHaveTextContent("(미충족)");
    await user.clear(next);
    await user.type(next, "newpass1!");
    expect(within(dialog).getByText("특수문자 포함")).toHaveTextContent("(충족)");
    const confirm = within(dialog).getByLabelText("새 비밀번호 확인");
    await user.type(confirm, "newpass1");
    expect(within(dialog).getByRole("status")).toHaveTextContent("비밀번호가 서로 달라요");
    expect(within(dialog).getByRole("button", { name: "변경 저장" })).toBeDisabled();
    await user.type(confirm, "!");
    expect(within(dialog).getByRole("status")).toHaveTextContent("비밀번호가 일치해요");

    await user.click(within(dialog).getByRole("button", { name: "변경 저장" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(mock.calls.change).toEqual([{ new_password: "newpass1!" }]);
    expect(await screen.findByText("비밀번호를 바꿨어요")).toBeInTheDocument();
  });

  it("이미 보낸 링크가 있으면 다시 보내지 않고, 보내기 오류는 창에 보여 준다", async () => {
    const mock = mockPasswordChange({
      available: true,
      state: "SENT",
      expires_at: new Date(Date.now() + 20 * 60_000).toISOString(),
    });
    server.use(
      http.post(apiUrl("/api/v1/me/password-change/link"), () =>
        HttpResponse.json(errorBody("rate_limited"), { status: 429 }),
      ),
    );
    const user = userEvent.setup();
    await renderRoute("/my/profile");
    await user.click(await screen.findByRole("button", { name: "비밀번호 재설정" }));
    const dialog = await screen.findByRole("dialog", { name: "비밀번호 변경" });
    expect(await within(dialog).findByText(/인증 링크를 보냈어요/)).toBeInTheDocument();
    expect(mock.calls.link).toBe(0);
    await user.click(within(dialog).getByRole("button", { name: "다시 보내기" }));
    expect(await within(dialog).findByText("오늘은 더 보낼 수 없어요. 내일 다시 시도해 주세요.")).toBeInTheDocument();
  });
});

describe("메일 링크 인증 (A72)", () => {
  it("토큰을 한 번만 확인하고 완료를 알려 준다", async () => {
    resetAuth();
    let calls = 0;
    server.use(
      http.post(apiUrl("/api/v1/auth/refresh"), () => HttpResponse.json(errorBody("x"), { status: 401 })),
      http.post(apiUrl("/api/v1/auth/password-change/verify"), () => {
        calls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    await renderRoute("/password-change/verify?token=abc");
    expect(await screen.findByRole("heading", { name: "이메일 인증이 완료되었습니다." })).toBeInTheDocument();
    expect(calls).toBe(1);
  });

  it("만료·사용된 링크는 쓸 수 없다고 알려 준다", async () => {
    resetAuth();
    server.use(
      http.post(apiUrl("/api/v1/auth/refresh"), () => HttpResponse.json(errorBody("x"), { status: 401 })),
      http.post(apiUrl("/api/v1/auth/password-change/verify"), () =>
        HttpResponse.json(errorBody("password_link_invalid"), { status: 400 }),
      ),
    );
    await renderRoute("/password-change/verify?token=old");
    expect(await screen.findByRole("heading", { name: "링크를 쓸 수 없어요" })).toBeInTheDocument();
  });
});
