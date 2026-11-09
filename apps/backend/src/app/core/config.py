"""애플리케이션 설정 (환경변수 / .env)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "oz-backoffice"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    # 로그인 후 돌려보낼 프론트엔드 주소 (성공: /, 실패: /login?error=<code>)
    frontend_base_url: str = "http://localhost:5173"

    # PostgreSQL (Tortoise 형식: postgres://user:pass@host:port/db)
    database_url: str = "postgres://oz:oz@localhost:5432/oz_backoffice"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    taskiq_redis_url: str = "redis://localhost:6379/1"

    # JWT
    jwt_secret_key: SecretStr = SecretStr("change-me-in-env")
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_seconds: int = 14 * 24 * 60 * 60
    # refresh 쿠키 Secure 속성.
    # 브라우저는 http://localhost도 보안 출처로 보므로 로컬에서도 true로 둔다
    refresh_cookie_secure: bool = True

    # Google OAuth2 (운영진 로그인)
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    # Google이 인가 code를 돌려보낼 백엔드 콜백 (Google Cloud Console에 같은 값을 등록한다)
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    google_allowed_domain: str = "nextrunners.co.kr"

    # Airtable 수강생 명단 (P5). 토큰은 읽기 범위(data.records:read, schema.bases:read)만
    airtable_token: SecretStr = SecretStr("")
    airtable_base_id: str = ""
    # 같은 Base의 두 테이블 (ID tbl... 또는 이름)
    airtable_student_table_id: str = ""  # 수강생 정보
    airtable_bootcamp_table_id: str = ""  # 과정-기수 (기수별 레코드, decisions A20)

    @property
    def airtable_configured(self) -> bool:
        return bool(
            self.airtable_token.get_secret_value()
            and self.airtable_base_id
            and self.airtable_student_table_id
            and self.airtable_bootcamp_table_id
        )

    # AWS S3 (비공개 버킷 1개 + prefix: contracts/, profiles/ ...)
    # 로컬·CI는 S3 에뮬레이터(floci)를 endpoint로 지정한다.
    # 운영은 endpoint 없이 AWS 기본 엔드포인트를 쓴다.
    aws_region: str = "ap-northeast-2"
    # 비워두면 boto 기본 자격 증명 체인(IAM 역할, 환경 프로파일)을 쓴다
    aws_access_key_id: str | None = None
    aws_secret_access_key: SecretStr | None = None
    s3_bucket: str = ""
    # 서버가 S3 API를 호출할 주소 (예: compose 내부 http://s3:4566)
    s3_endpoint_url: str | None = None
    # 브라우저에 주는 presigned URL을 서명할 주소 (예: http://localhost:4566)
    # 없으면 s3_endpoint_url을 쓴다
    s3_public_endpoint_url: str | None = None
    s3_presigned_get_ttl_seconds: int = 10 * 60
    s3_presigned_post_ttl_seconds: int = 10 * 60

    # 업무상 날짜 경계 기준 타임존
    business_timezone: str = "Asia/Seoul"


@lru_cache
def get_settings() -> Settings:
    return Settings()
