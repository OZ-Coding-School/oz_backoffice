from datetime import date
from typing import Any

import httpx
import pytest
import respx

from app.core.config import Settings
from app.core.holidays import build_holiday_source
from app.integrations.data_go_kr.holidays import (
    URL,
    DataGoKrHolidayClient,
    FixedHolidaySource,
    parse_holidays,
)
from app.shared.errors import ServiceUnavailableError

pytestmark = pytest.mark.unit


def payload(items: Any, code: str = "00") -> dict[str, Any]:
    return {
        "response": {
            "header": {"resultCode": code, "resultMsg": "NORMAL SERVICE."},
            "body": {"items": items, "numOfRows": 100, "pageNo": 1, "totalCount": 0},
        }
    }


def item(locdate: int, name: str, is_holiday: str = "Y") -> dict[str, Any]:
    return {"dateKind": "01", "dateName": name, "isHoliday": is_holiday, "locdate": locdate}


def test_parse_list_single_and_empty() -> None:
    many = payload({"item": [item(20260101, "1월1일"), item(20260717, "제헌절", "N")]})
    assert parse_holidays(many) == [(date(2026, 1, 1), "1월1일")]  # isHoliday=N 제외
    single = payload({"item": item(20260815, "광복절")})
    assert parse_holidays(single) == [(date(2026, 8, 15), "광복절")]
    assert parse_holidays(payload("")) == []


@pytest.mark.parametrize(
    "bad", [payload("", code="30"), {"unexpected": 1}, payload({"item": [{"isHoliday": "Y"}]})]
)
def test_parse_rejects_errors(bad: Any) -> None:
    with pytest.raises(ServiceUnavailableError) as e:
        parse_holidays(bad)
    assert e.value.code == "holiday_sync_failed"


@respx.mock
async def test_client_sends_year_and_key() -> None:
    route = respx.get(URL).respond(200, json=payload({"item": item(20270101, "1월1일")}))
    async with httpx.AsyncClient() as http:
        found = await DataGoKrHolidayClient("key", http).fetch_year(2027)
    assert found == [(date(2027, 1, 1), "1월1일")]
    params = route.calls.last.request.url.params
    assert (params["solYear"], params["serviceKey"], params["_type"]) == ("2027", "key", "json")


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(200, text="<OpenAPI_ServiceResponse>SERVICE_KEY_IS_NOT_REGISTERED"),
    ],
)
async def test_client_failures(response: httpx.Response) -> None:
    respx.get(URL).mock(return_value=response)
    async with httpx.AsyncClient() as http:
        with pytest.raises(ServiceUnavailableError):
            await DataGoKrHolidayClient("key", http).fetch_year(2027)


async def test_build_source_by_driver(settings: Settings) -> None:
    async with httpx.AsyncClient() as http:
        assert isinstance(build_holiday_source(settings, http), FixedHolidaySource)
        real = settings.model_copy(update={"holiday_driver": "data_go_kr"})
        assert build_holiday_source(real, http) is None  # 키 없음
        keyed = real.model_copy(update={"holiday_api_key": real.holiday_api_key.__class__("k")})
        assert isinstance(build_holiday_source(keyed, http), DataGoKrHolidayClient)
    fixed = await FixedHolidaySource().fetch_year(2026)
    assert len(fixed) == 22
