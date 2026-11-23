import { createSseParser, reconnectDelay } from "./sse";

describe("SSE 파서 (A58)", () => {
  it("이벤트 이름·data를 읽고 주석·retry는 건너뛴다", () => {
    const parse = createSseParser();
    expect(parse('retry: 3000\nevent: ready\ndata: {}\n\n: ping\n\nevent: message\ndata: {"id":1}\n\n')).toEqual([
      { event: "ready", data: "{}" },
      { event: "message", data: '{"id":1}' },
    ]);
  });

  it("조각이 중간에서 끊겨도 이어 읽고, CRLF·여러 줄 data를 받는다", () => {
    const parse = createSseParser();
    expect(parse("event: read\r\nda")).toEqual([]);
    expect(parse("ta: a\r\ndata: b\r\n\r\nevent: x")).toEqual([{ event: "read", data: "a\nb" }]);
    expect(parse("\ndata: c\n\n")).toEqual([{ event: "x", data: "c" }]);
  });

  it("다시 연결은 3초부터 두 배, 최대 30초", () => {
    expect([0, 1, 2, 3, 4].map(reconnectDelay)).toEqual([3_000, 6_000, 12_000, 24_000, 30_000]);
  });
});
