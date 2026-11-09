"""도메인/응용 계층 공통 예외 (프레임워크 무관).

HTTP 상태 코드 매핑은 app.core.errors가 담당한다.
"""


class AppError(Exception):
    default_code = "app_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code


class NotFoundError(AppError):
    default_code = "not_found"


class ConflictError(AppError):
    default_code = "conflict"


class BusinessRuleViolation(AppError):
    """도메인 규칙 위반 (예: 잔여 시간 부족, 허용되지 않은 상태 전이)."""

    default_code = "business_rule_violation"


class AuthenticationError(AppError):
    default_code = "unauthenticated"


class PermissionDeniedError(AppError):
    default_code = "permission_denied"


class ServiceUnavailableError(AppError):
    """설정되지 않았거나 일시적으로 쓸 수 없는 기능 (예: Google OAuth 클라이언트 미설정)."""

    default_code = "service_unavailable"


class TooManyRequestsError(AppError):
    """요청 횟수 제한 초과 (발송 레이트 리밋, 재발송 간격).

    retry_after는 다시 시도할 수 있기까지 남은 초다(응답 헤더 Retry-After).
    """

    default_code = "too_many_requests"

    def __init__(self, message: str, *, retry_after: int, code: str | None = None) -> None:
        super().__init__(message, code=code)
        self.retry_after = max(1, retry_after)
