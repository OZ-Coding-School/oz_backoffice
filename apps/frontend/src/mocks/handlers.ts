import type { RequestHandler } from "msw";

/**
 * 로컬 개발(VITE_API_MOCKING=true)과 테스트가 함께 쓰는 기본 핸들러.
 * 테스트별 응답은 `server.use(...)`로 덮어쓴다.
 */
export const handlers: RequestHandler[] = [];
