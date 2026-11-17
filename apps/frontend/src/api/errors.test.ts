import { ApiError, isRetryableError, toApiError } from "./errors";

describe("API 오류 변환", () => {
  it("백엔드 오류 응답의 코드와 메시지를 쓴다", () => {
    const error = toApiError(409, { error: { code: "already_registered", message: "이미 가입된 이메일입니다." } });
    expect(error).toMatchObject({ status: 409, code: "already_registered", message: "이미 가입된 이메일입니다." });
  });

  it("422 검증 오류는 필드별 메시지로 바꾼다", () => {
    const error = toApiError(422, {
      detail: [
        { type: "missing", loc: ["body", "email"], msg: "Field required" },
        { type: "too_short", loc: ["body", "items", 0, "name"], msg: "too short" },
        { type: "missing", loc: ["query", "limit"], msg: "bad limit" },
        { type: "missing", loc: ["body", "email"], msg: "두 번째 메시지는 버린다" },
      ],
    });
    expect(error.code).toBe("validation_error");
    expect(error.fieldErrors).toEqual({ email: "Field required", "items.0.name": "too short", limit: "bad limit" });
  });

  it("알 수 없는 본문은 상태 코드로 만든다", () => {
    expect(toApiError(502, "<html>")).toMatchObject({ status: 502, code: "http_502" });
    expect(toApiError(500, null).message).toContain("잠시 후 다시 시도");
  });

  it("네트워크 오류·5xx만 다시 시도한다", () => {
    expect(isRetryableError(new TypeError("Failed to fetch"))).toBe(true);
    expect(isRetryableError(new ApiError(503, "http_503", ""))).toBe(true);
    expect(isRetryableError(new ApiError(404, "not_found", ""))).toBe(false);
    expect(isRetryableError(new ApiError(401, "token_expired", ""))).toBe(false);
  });
});

describe("Retry-After", () => {
  it("429의 남은 초를 읽는다", () => {
    const error = toApiError(429, { error: { code: "login_locked", message: "잠김" } }, "120");
    expect(error.retryAfterSeconds).toBe(120);
    expect(toApiError(429, { error: { code: "x", message: "" } }, "abc").retryAfterSeconds).toBeNull();
  });
});
