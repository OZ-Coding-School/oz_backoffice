import { http, HttpResponse } from "msw";

import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";

import { api, ApiError, REFRESH_AHEAD_MS, unwrap } from "./client";
import { REFRESH_LOCK } from "./refresh";
import { onSessionEnded, resetSessionForTest, setAccessToken, useSession } from "./session";

const ME = {
  id: "u1",
  email: "a@gmail.com",
  name: "가수강",
  phone_number: null,
  approval_status: "APPROVED",
  approved_at: null,
  roles: [],
};

function inMinutes(minutes: number): string {
  return new Date(Date.now() + minutes * 60_000).toISOString();
}

/** /auth/refresh 모킹. 호출 수를 센다. */
function mockRefresh(result: "ok" | { status: number; code: string }) {
  const calls = { count: 0 };
  server.use(
    http.post(apiUrl("/api/v1/auth/refresh"), async () => {
      calls.count += 1;
      await new Promise((resolve) => setTimeout(resolve, 10));
      if (result === "ok") return HttpResponse.json({ access_token: `new-${calls.count}`, expires_at: inMinutes(15) });
      return HttpResponse.json(errorBody(result.code), { status: result.status });
    }),
  );
  return calls;
}

/** /me 모킹: `new-`로 시작하는 토큰만 받는다 (갱신 후 재시도 확인용). */
function mockMe() {
  const seen: (string | null)[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me"), ({ request }) => {
      const auth = request.headers.get("Authorization");
      seen.push(auth);
      if (!auth?.startsWith("Bearer new-")) return HttpResponse.json(errorBody("token_expired"), { status: 401 });
      return HttpResponse.json(ME);
    }),
  );
  return seen;
}

beforeEach(() => resetSessionForTest());
afterEach(() => vi.unstubAllGlobals());

describe("API 클라이언트 인증", () => {
  it("세션의 access 토큰을 Authorization 헤더로 보낸다", async () => {
    setAccessToken("new-0", inMinutes(15));
    const seen = mockMe();
    await expect(unwrap(api.GET("/api/v1/me"))).resolves.toMatchObject({ name: "가수강" });
    expect(seen).toEqual(["Bearer new-0"]);
  });

  it("만료가 30초 안으로 남았으면 요청 전에 미리 갱신한다", async () => {
    setAccessToken("old", new Date(Date.now() + REFRESH_AHEAD_MS - 1_000).toISOString());
    const refresh = mockRefresh("ok");
    const seen = mockMe();
    await unwrap(api.GET("/api/v1/me"));
    expect(refresh.count).toBe(1);
    expect(seen).toEqual(["Bearer new-1"]);
  });

  it("401이면 한 번 갱신하고 다시 보낸다", async () => {
    setAccessToken("old", inMinutes(15));
    const refresh = mockRefresh("ok");
    const seen = mockMe();
    await expect(unwrap(api.GET("/api/v1/me"))).resolves.toMatchObject({ id: "u1" });
    expect(refresh.count).toBe(1);
    expect(seen).toEqual(["Bearer old", "Bearer new-1"]);
  });

  it("동시에 401을 받은 요청들은 갱신 하나를 같이 기다린다", async () => {
    setAccessToken("old", inMinutes(15));
    const refresh = mockRefresh("ok");
    mockMe();
    await Promise.all([unwrap(api.GET("/api/v1/me")), unwrap(api.GET("/api/v1/me")), unwrap(api.GET("/api/v1/me"))]);
    expect(refresh.count).toBe(1);
  });

  it("다시 보내도 401이면 더 갱신하지 않고 오류를 돌려준다", async () => {
    setAccessToken("old", inMinutes(15));
    const refresh = mockRefresh("ok");
    server.use(http.get(apiUrl("/api/v1/me"), () => HttpResponse.json(errorBody("token_invalid"), { status: 401 })));
    const error = await unwrap(api.GET("/api/v1/me")).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 401, code: "token_invalid" });
    expect(refresh.count).toBe(1);
  });

  it("로그인하지 않았으면 갱신하지 않는다", async () => {
    const refresh = mockRefresh("ok");
    const seen = mockMe();
    await expect(unwrap(api.GET("/api/v1/me"))).rejects.toMatchObject({ status: 401 });
    expect(refresh.count).toBe(0);
    expect(seen).toEqual([null]);
  });

  it("갱신이 401이면 세션을 끝내고 사유를 남기며 구독자에게 알린다", async () => {
    setAccessToken("old", inMinutes(15));
    mockRefresh({ status: 401, code: "refresh_token_reused" });
    mockMe();
    const ended = vi.fn<(reason: string) => void>();
    onSessionEnded(ended);

    await expect(unwrap(api.GET("/api/v1/me"))).rejects.toMatchObject({ status: 401 });
    expect(useSession.getState()).toMatchObject({ accessToken: null, endedReason: "refresh_token_reused" });
    expect(ended).toHaveBeenCalledWith("refresh_token_reused");
  });

  it("갱신 중 서버 오류면 세션을 유지한다", async () => {
    setAccessToken("old", inMinutes(15));
    mockRefresh({ status: 503, code: "unavailable" });
    mockMe();
    await expect(unwrap(api.GET("/api/v1/me"))).rejects.toMatchObject({ status: 401 });
    expect(useSession.getState()).toMatchObject({ accessToken: "old", endedReason: null });
  });

  it("탭 간 잠금(Web Locks)을 잡고 갱신한다", async () => {
    const request = vi.fn<(name: string, task: () => Promise<boolean>) => Promise<boolean>>((_name, task) => task());
    vi.stubGlobal("navigator", { ...navigator, locks: { request } });
    setAccessToken("old", inMinutes(15));
    mockRefresh("ok");
    mockMe();
    await unwrap(api.GET("/api/v1/me"));
    expect(request).toHaveBeenCalledTimes(1);
    expect(request.mock.calls[0]?.[0]).toBe(REFRESH_LOCK);
  });

  it("요청 본문이 있는 요청도 갱신 후 같은 본문으로 다시 보낸다", async () => {
    setAccessToken("old", inMinutes(15));
    mockRefresh("ok");
    const bodies: unknown[] = [];
    server.use(
      http.put(apiUrl("/api/v1/me/mentor-schedule/accepting"), async ({ request }) => {
        bodies.push(await request.json());
        if (request.headers.get("Authorization") !== "Bearer new-1") {
          return HttpResponse.json(errorBody("token_expired"), { status: 401 });
        }
        return HttpResponse.json({ mentor_id: "m1", accepting_requests: true, canceled_pending_requests: 0 });
      }),
    );
    await unwrap(api.PUT("/api/v1/me/mentor-schedule/accepting", { body: { accepting_requests: true } }));
    expect(bodies).toEqual([{ accepting_requests: true }, { accepting_requests: true }]);
  });
});
