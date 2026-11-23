/** SSE 한 건 (`event:`·`data:` 줄). 주석(`:`)과 `retry:`는 건너뛴다 */
export interface SseEvent {
  event: string;
  data: string;
}

/**
 * 텍스트 조각을 받아 끝난 이벤트만 돌려주는 SSE 파서 (A58: Authorization 헤더 때문에 EventSource 대신 fetch).
 * 조각이 이벤트 중간에서 끊겨도 다음 조각과 이어 붙여 읽는다. CRLF도 받는다.
 */
export function createSseParser(): (chunk: string) => SseEvent[] {
  let buffer = "";
  return (chunk) => {
    buffer += chunk.replace(/\r\n?/g, "\n");
    const events: SseEvent[] = [];
    let end = buffer.indexOf("\n\n");
    while (end !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (!line || line.startsWith(":")) continue;
        const colon = line.indexOf(":");
        const field = colon === -1 ? line : line.slice(0, colon);
        const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
        if (field === "event") event = value;
        else if (field === "data") data.push(value);
      }
      if (data.length > 0) events.push({ event, data: data.join("\n") });
      end = buffer.indexOf("\n\n");
    }
    return events;
  };
}

/** 다시 연결 대기: 3초부터 두 배씩, 최대 30초 (F41) */
export function reconnectDelay(attempt: number): number {
  return Math.min(30_000, 3_000 * 2 ** Math.max(0, attempt));
}
