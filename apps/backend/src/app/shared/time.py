"""시간 관련 순수 유틸 (도메인에서도 사용)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def business_date(at: datetime, tz: ZoneInfo = KST) -> date:
    """업무상 날짜 (기본 KST 기준 하루 경계)."""
    if at.tzinfo is None:
        raise ValueError("tz-aware datetime이 필요합니다.")
    return at.astimezone(tz).date()
