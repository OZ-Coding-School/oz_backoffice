import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";

import { server } from "@/mocks/node";

// jsdom에 없는 브라우저 API (라우터 스크롤 복원이 부른다)
window.scrollTo = () => {};

// 모킹하지 않은 API 요청은 실패로 본다 (실제 네트워크 호출 금지)
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());
