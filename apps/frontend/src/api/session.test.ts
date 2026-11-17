import { endSession, hasSession, onSessionEnded, resetSessionForTest, setAccessToken, useSession } from "./session";

beforeEach(() => resetSessionForTest());

function nextMessage(channel: BroadcastChannel): Promise<unknown> {
  return new Promise((resolve) => channel.addEventListener("message", (event) => resolve(event.data), { once: true }));
}

describe("세션", () => {
  it("access 토큰과 만료 시각을 메모리에 둔다", () => {
    setAccessToken("token", "2026-11-17T10:00:00Z");
    expect(useSession.getState()).toMatchObject({
      accessToken: "token",
      expiresAt: Date.parse("2026-11-17T10:00:00Z"),
    });
    expect(hasSession()).toBe(true);
    expect(window.localStorage.length).toBe(0);
  });

  it("세션이 끝나면 다른 탭에 알린다", async () => {
    const otherTab = new BroadcastChannel("oz-auth");
    const received = nextMessage(otherTab);
    setAccessToken("token", "2026-11-17T10:00:00Z");
    endSession("refresh_token_reused");
    await expect(received).resolves.toEqual({ type: "session-ended", reason: "refresh_token_reused" });
    otherTab.close();
  });

  it("다른 탭이 끝냈다고 알리면 이 탭도 세션을 끝낸다", async () => {
    setAccessToken("token", "2026-11-17T10:00:00Z");
    const ended = new Promise<string>((resolve) => onSessionEnded(resolve));
    const otherTab = new BroadcastChannel("oz-auth");
    otherTab.postMessage({ type: "session-ended", reason: "refresh_token_revoked" });
    await expect(ended).resolves.toBe("refresh_token_revoked");
    expect(useSession.getState()).toMatchObject({ accessToken: null, endedReason: "refresh_token_revoked" });
    otherTab.close();
  });
});
