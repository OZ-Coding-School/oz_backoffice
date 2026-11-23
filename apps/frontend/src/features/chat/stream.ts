import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useEffectEvent } from "react";

import { refreshAccessToken } from "@/api/refresh";
import { useSession } from "@/api/session";
import { env } from "@/env";
import { createSseParser, reconnectDelay, type SseEvent } from "@/lib/sse";

import { useApplyMessage, useApplyThread, type ChatMessage, type ChatThread } from "./api";

/**
 * 채팅 실시간 수신 (A58·F41). 로그인한 동안 탭마다 연결 하나.
 * - Authorization 헤더로 연결하고, 토큰이 바뀌면(갱신) 다시 연결한다. 401이면 갱신을 한 번 시도한다.
 * - 끊기면 3초부터 최대 30초까지 늘려 다시 연결한다.
 * - 끊긴 사이의 알림은 다시 오지 않으므로 다시 연결되면(`ready`) 채팅 조회를 모두 다시 한다.
 */
export function useChatStream(enabled: boolean) {
  const queryClient = useQueryClient();
  const applyMessage = useApplyMessage();
  const applyThread = useApplyThread();
  const token = useSession((s) => s.accessToken);

  const handle = useEffectEvent((event: SseEvent, reconnected: boolean) => {
    if (event.event === "ready") {
      if (reconnected) void queryClient.invalidateQueries({ queryKey: ["chat"] });
      return;
    }
    if (event.event === "message" || event.event === "message_deleted") {
      applyMessage(JSON.parse(event.data) as ChatMessage);
    } else if (event.event === "read") {
      applyThread(JSON.parse(event.data) as ChatThread);
    }
  });

  useEffect(() => {
    if (!enabled || !token) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let connectedOnce = false;

    const connect = async () => {
      try {
        const response = await fetch(`${env.apiBaseUrl}/me/mentoring/chat/stream`, {
          headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
          credentials: "include",
          signal: controller.signal,
        });
        if (response.status === 401) {
          // 토큰이 바뀌면 이 효과가 다시 돌며 새로 연결한다. 세션이 끝났으면 토큰이 비어 멈춘다
          await refreshAccessToken().catch(() => false);
          return;
        }
        if (!response.ok || !response.body) throw new Error(`stream ${response.status}`);
        const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
        const parse = createSseParser();
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          for (const event of parse(value)) {
            if (event.event === "ready") {
              handle(event, connectedOnce);
              connectedOnce = true;
              attempt = 0;
            } else {
              handle(event, false);
            }
          }
        }
      } catch {
        // 끊김·네트워크 오류: 아래에서 다시 연결한다
      }
      if (controller.signal.aborted) return;
      timer = setTimeout(() => void connect(), reconnectDelay(attempt));
      attempt += 1;
    };

    void connect();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [enabled, token]);
}
