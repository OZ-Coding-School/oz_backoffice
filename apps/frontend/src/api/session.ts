import { create } from "zustand";

/**
 * 로그인 세션 (클라이언트 전용 상태, decisions F2·A7).
 * access 토큰은 메모리에만 둔다. 저장소(localStorage 등)에 쓰지 않는다.
 */
export interface SessionState {
  accessToken: string | null;
  /** access 토큰 만료 시각 (epoch ms) */
  expiresAt: number | null;
  /** 세션이 끝난 사유 (서버 오류 코드, 예: refresh_token_reused). 로그인 화면 안내에 쓴다 (FE-1a) */
  endedReason: string | null;
}

export const useSession = create<SessionState>(() => ({ accessToken: null, expiresAt: null, endedReason: null }));

export function setAccessToken(accessToken: string, expiresAt: string): void {
  useSession.setState({ accessToken, expiresAt: new Date(expiresAt).getTime(), endedReason: null });
}

export function hasSession(): boolean {
  return useSession.getState().accessToken !== null;
}

const CHANNEL = "oz-auth";
type SessionMessage = { type: "session-ended"; reason: string };

const endedListeners = new Set<(reason: string) => void>();
let channel: BroadcastChannel | null = null;

function getChannel(): BroadcastChannel | null {
  if (typeof BroadcastChannel === "undefined") return null;
  if (!channel) {
    channel = new BroadcastChannel(CHANNEL);
    channel.addEventListener("message", (event: MessageEvent<SessionMessage>) => {
      if (event.data?.type === "session-ended") endSession(event.data.reason, { broadcast: false });
    });
  }
  return channel;
}

/**
 * 세션을 끝낸다: access 토큰을 지우고 사유를 남긴 뒤 구독자(Query 캐시 비우기 등)에 알린다.
 * 이 탭에 세션이 있었으면 다른 탭에도 알려 함께 로그아웃한다 (decisions F19).
 */
export function endSession(reason: string, { broadcast = true }: { broadcast?: boolean } = {}): void {
  const hadSession = hasSession();
  useSession.setState({ accessToken: null, expiresAt: null, endedReason: reason });
  endedListeners.forEach((listener) => listener(reason));
  if (broadcast && hadSession) getChannel()?.postMessage({ type: "session-ended", reason } satisfies SessionMessage);
}

/** 세션이 끝날 때 할 일을 등록한다 (예: Query 캐시 비우기). 다른 탭의 알림도 받기 시작한다. */
export function onSessionEnded(listener: (reason: string) => void): () => void {
  getChannel();
  endedListeners.add(listener);
  return () => endedListeners.delete(listener);
}

/** 테스트용: 세션과 탭 간 채널을 초기 상태로 되돌린다. */
export function resetSessionForTest(): void {
  useSession.setState({ accessToken: null, expiresAt: null, endedReason: null });
  endedListeners.clear();
  channel?.close();
  channel = null;
}
