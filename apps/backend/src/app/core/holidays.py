"""설정으로 법정공휴일 출처를 고른다 (decisions A95·B16).

`HOLIDAY_DRIVER=fixed`(기본)는 고정 자료, `data_go_kr`는 특일 정보 API를 호출한다.
data_go_kr인데 서비스 키가 없으면 None을 주고, 동기화는 건너뛰거나(워커) 503을 준다(API).
"""

import logging

import httpx

from app.core.config import Settings
from app.integrations.data_go_kr.holidays import DataGoKrHolidayClient, FixedHolidaySource

logger = logging.getLogger(__name__)


def build_holiday_source(
    settings: Settings, http: httpx.AsyncClient
) -> DataGoKrHolidayClient | FixedHolidaySource | None:
    if settings.holiday_driver == "fixed":
        return FixedHolidaySource()
    key = settings.holiday_api_key.get_secret_value()
    if not key:
        logger.warning(
            "공휴일 동기화 비활성: HOLIDAY_DRIVER=data_go_kr에는 HOLIDAY_API_KEY가 필요합니다."
        )
        return None
    return DataGoKrHolidayClient(key, http)
