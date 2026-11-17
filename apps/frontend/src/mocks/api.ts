import { env } from "@/env";
import type { paths } from "@/api/schema.gen";

/**
 * MSW 핸들러용 전체 URL. 생성 타입의 경로만 받으므로 없는 API를 모킹하면 타입 오류가 난다.
 * 경로 변수 `{id}`는 MSW 형식 `:id`로 바꾼다.
 * 예: `http.get(apiUrl("/api/v1/me"), () => HttpResponse.json(...))`
 */
export function apiUrl(path: keyof paths): string {
  return `${env.backendUrl}${path.replace(/\{(\w+)\}/g, ":$1")}`;
}

/** 백엔드 오류 응답 본문 `{"error": {"code", "message"}}` */
export function errorBody(code: string, message = "오류") {
  return { error: { code, message } };
}
