"""한국천문연구원 특일 정보 API(getRestDeInfo) 어댑터 (decisions A95·B16).

`isHoliday=Y`인 날만 공휴일로 본다. 항목이 하나면 `item`이 객체, 없으면 `items`가 빈 문자열로
온다. 서비스 키가 잘못되면 JSON 대신 XML 오류를 주므로 JSON이 아니면 실패로 본다.
"""

import logging
from datetime import date
from typing import Any

import httpx

from app.shared.errors import ServiceUnavailableError

logger = logging.getLogger(__name__)

URL = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
FAILED = "공휴일 정보를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요."


def _failed() -> ServiceUnavailableError:
    return ServiceUnavailableError(FAILED, code="holiday_sync_failed")


def parse_holidays(payload: Any) -> list[tuple[date, str]]:
    """응답 JSON → (날짜, 이름). 형식이 다르면 ServiceUnavailableError."""
    try:
        response = payload["response"]
        if response["header"]["resultCode"] != "00":
            raise _failed()
        items = response["body"]["items"]
        raw = items["item"] if isinstance(items, dict) else []
        rows = raw if isinstance(raw, list) else [raw]
        found = []
        for row in rows:
            if row.get("isHoliday") != "Y":
                continue
            day = str(row["locdate"])
            found.append((date(int(day[:4]), int(day[4:6]), int(day[6:8])), str(row["dateName"])))
        return found
    except (KeyError, TypeError, ValueError) as e:
        raise _failed() from e


class DataGoKrHolidayClient:
    def __init__(self, service_key: str, http: httpx.AsyncClient) -> None:
        self._key = service_key
        self._http = http

    async def fetch_year(self, year: int) -> list[tuple[date, str]]:
        params: dict[str, str | int] = {
            "serviceKey": self._key,
            "solYear": year,
            "numOfRows": 100,
            "_type": "json",
        }
        try:
            response = await self._http.get(URL, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("특일 정보 API 호출 실패 (%s년): %s", year, type(e).__name__)
            raise _failed() from e
        return parse_holidays(payload)


# 개발·테스트용 고정 자료 (HOLIDAY_DRIVER=fixed). 2025~2027 공휴일
FIXED_HOLIDAYS: tuple[tuple[date, str], ...] = (
    (date(2025, 1, 1), "1월1일"),
    (date(2025, 1, 27), "임시공휴일"),
    (date(2025, 1, 28), "설날"),
    (date(2025, 1, 29), "설날"),
    (date(2025, 1, 30), "설날"),
    (date(2025, 3, 1), "삼일절"),
    (date(2025, 3, 3), "대체공휴일"),
    (date(2025, 5, 5), "어린이날"),
    (date(2025, 5, 5), "부처님오신날"),
    (date(2025, 5, 6), "대체공휴일"),
    (date(2025, 6, 3), "대통령선거일"),
    (date(2025, 6, 6), "현충일"),
    (date(2025, 8, 15), "광복절"),
    (date(2025, 10, 3), "개천절"),
    (date(2025, 10, 5), "추석"),
    (date(2025, 10, 6), "추석"),
    (date(2025, 10, 7), "추석"),
    (date(2025, 10, 8), "대체공휴일"),
    (date(2025, 10, 9), "한글날"),
    (date(2025, 12, 25), "기독탄신일"),
    (date(2026, 1, 1), "1월1일"),
    (date(2026, 2, 16), "설날"),
    (date(2026, 2, 17), "설날"),
    (date(2026, 2, 18), "설날"),
    (date(2026, 3, 1), "삼일절"),
    (date(2026, 3, 2), "대체공휴일"),
    (date(2026, 5, 1), "노동절"),
    (date(2026, 5, 5), "어린이날"),
    (date(2026, 5, 24), "부처님오신날"),
    (date(2026, 5, 25), "대체공휴일"),
    (date(2026, 6, 3), "전국동시지방선거"),
    (date(2026, 6, 6), "현충일"),
    (date(2026, 7, 17), "제헌절"),
    (date(2026, 8, 15), "광복절"),
    (date(2026, 8, 17), "대체공휴일"),
    (date(2026, 9, 24), "추석"),
    (date(2026, 9, 25), "추석"),
    (date(2026, 9, 26), "추석"),
    (date(2026, 10, 3), "개천절"),
    (date(2026, 10, 5), "대체공휴일"),
    (date(2026, 10, 9), "한글날"),
    (date(2026, 12, 25), "기독탄신일"),
    (date(2027, 1, 1), "1월1일"),
    (date(2027, 2, 6), "설날"),
    (date(2027, 2, 7), "설날"),
    (date(2027, 2, 8), "설날"),
    (date(2027, 2, 9), "대체공휴일"),
    (date(2027, 3, 1), "삼일절"),
    (date(2027, 5, 1), "노동절"),
    (date(2027, 5, 3), "대체공휴일"),
    (date(2027, 5, 5), "어린이날"),
    (date(2027, 5, 13), "부처님오신날"),
    (date(2027, 6, 6), "현충일"),
    (date(2027, 7, 17), "제헌절"),
    (date(2027, 7, 19), "대체공휴일"),
    (date(2027, 8, 15), "광복절"),
    (date(2027, 8, 16), "대체공휴일"),
    (date(2027, 9, 14), "추석"),
    (date(2027, 9, 15), "추석"),
    (date(2027, 9, 16), "추석"),
    (date(2027, 10, 3), "개천절"),
    (date(2027, 10, 4), "대체공휴일"),
    (date(2027, 10, 9), "한글날"),
    (date(2027, 10, 11), "대체공휴일"),
    (date(2027, 12, 25), "기독탄신일"),
    (date(2027, 12, 27), "대체공휴일"),
)


class FixedHolidaySource:
    """외부 호출 없이 고정 자료를 준다 (개발·테스트)."""

    async def fetch_year(self, year: int) -> list[tuple[date, str]]:
        return [(day, name) for day, name in FIXED_HOLIDAYS if day.year == year]
