"""예외 → HTTP 응답 매핑.

응답 형식: {"error": {"code": "...", "message": "..."}}
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette import status
from tortoise.exceptions import IntegrityError

from app.shared.errors import (
    AppError,
    AuthenticationError,
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    TooManyRequestsError,
)

logger = logging.getLogger(__name__)

_STATUS_BY_ERROR: dict[type[AppError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    BusinessRuleViolation: status.HTTP_422_UNPROCESSABLE_CONTENT,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    ServiceUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
    TooManyRequestsError: status.HTTP_429_TOO_MANY_REQUESTS,
}


def status_for(error: AppError) -> int:
    for error_type in type(error).__mro__:
        if error_type in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[error_type]
    return status.HTTP_400_BAD_REQUEST


def error_body(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        return await unhandled_error_handler(request, exc)
    headers = (
        {"Retry-After": str(exc.retry_after)} if isinstance(exc, TooManyRequestsError) else None
    )
    return JSONResponse(
        status_code=status_for(exc), content=error_body(exc.code, exc.message), headers=headers
    )


async def integrity_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """서비스가 미리 검사하지 못한 DB 제약 위반(동시 요청 경합 등)의 안전망. 409로 응답한다."""
    logger.warning("DB 제약 위반", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=error_body("conflict", "다른 요청과 충돌했습니다. 다시 시도해 주세요."),
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("처리되지 않은 예외", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body("internal_error", "서버 오류가 발생했습니다."),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
