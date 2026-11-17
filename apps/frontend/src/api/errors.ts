/**
 * API 오류. 백엔드 오류 응답 `{"error": {"code", "message"}}`과 요청 검증 오류(422 `{"detail": [...]}`)를
 * 하나의 형태로 바꾼다. 화면 문구는 기능별 오류 코드 표(messages.ts)에서 고르고, 없으면 message를 보여 준다.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  /** 422 요청 검증 오류의 필드별 메시지 (키: `email`, `items.0.name` …) */
  readonly fieldErrors: Readonly<Record<string, string>>;

  constructor(status: number, code: string, message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
  }
}

const FALLBACK_MESSAGE = "요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.";
const VALIDATION_MESSAGE = "입력한 값을 확인해 주세요.";
/** 검증 오류 위치 중 필드 이름이 아닌 앞부분 */
const LOCATION_PREFIXES = new Set(["body", "query", "path", "header", "cookie"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function toApiError(status: number, body: unknown): ApiError {
  if (isRecord(body) && isRecord(body.error) && typeof body.error.code === "string") {
    const message = typeof body.error.message === "string" ? body.error.message : FALLBACK_MESSAGE;
    return new ApiError(status, body.error.code, message);
  }
  if (status === 422 && isRecord(body) && Array.isArray(body.detail)) {
    const fieldErrors: Record<string, string> = {};
    for (const item of body.detail) {
      if (!isRecord(item) || !Array.isArray(item.loc)) continue;
      const loc = item.loc.map(String);
      const field = (LOCATION_PREFIXES.has(loc[0] ?? "") ? loc.slice(1) : loc).join(".");
      if (field && !(field in fieldErrors))
        fieldErrors[field] = typeof item.msg === "string" ? item.msg : VALIDATION_MESSAGE;
    }
    return new ApiError(status, "validation_error", VALIDATION_MESSAGE, fieldErrors);
  }
  return new ApiError(status, `http_${status}`, FALLBACK_MESSAGE);
}

/** 응답 본문을 읽어 ApiError로 바꾼다 (JSON이 아니면 상태 코드만으로). */
export async function readApiError(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null);
  return toApiError(response.status, body);
}

/** 다시 시도해 볼 만한 오류인가: 네트워크 오류·5xx만 (4xx는 같은 결과, decisions F19). */
export function isRetryableError(error: unknown): boolean {
  return !(error instanceof ApiError) || error.status >= 500;
}
