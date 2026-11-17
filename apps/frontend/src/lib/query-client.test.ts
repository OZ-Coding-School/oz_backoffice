import { ApiError } from "@/api/errors";

import { createQueryClient } from "./query-client";

describe("Query 기본값", () => {
  const retry = createQueryClient().getDefaultOptions().queries?.retry;
  if (typeof retry !== "function") throw new Error("retry는 함수여야 한다");

  it("네트워크 오류·5xx는 한 번만 다시 시도한다", () => {
    expect(retry(0, new TypeError("Failed to fetch"))).toBe(true);
    expect(retry(0, new ApiError(500, "http_500", ""))).toBe(true);
    expect(retry(1, new ApiError(500, "http_500", ""))).toBe(false);
  });

  it("4xx는 다시 시도하지 않는다", () => {
    expect(retry(0, new ApiError(403, "forbidden", ""))).toBe(false);
  });
});
