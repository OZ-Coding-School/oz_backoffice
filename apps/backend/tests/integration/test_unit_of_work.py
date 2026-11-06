from collections.abc import Awaitable, Callable

import pytest
from tortoise import connections

from app.core.uow import UnitOfWork

pytestmark = pytest.mark.integration


class Rollback(Exception):
    pass


async def _fail_inside_uow(work: Callable[[UnitOfWork], Awaitable[None]]) -> None:
    async with UnitOfWork() as uow:
        await work(uow)
        raise Rollback


async def test_database_connection() -> None:
    _, rows = await connections.get("default").execute_query("SELECT 1 AS one")
    assert rows[0]["one"] == 1


async def test_on_commit_runs_only_after_successful_commit() -> None:
    calls: list[str] = []

    async def after() -> None:
        calls.append("committed")

    async with UnitOfWork() as uow:
        uow.on_commit(after)
        assert calls == []
    assert calls == ["committed"]

    async def register(uow: UnitOfWork) -> None:
        uow.on_commit(after)

    with pytest.raises(Rollback):
        await _fail_inside_uow(register)
    assert calls == ["committed"]


async def test_rollback_discards_writes() -> None:
    conn = connections.get("default")
    await conn.execute_script("CREATE TABLE IF NOT EXISTS _uow_probe (id int primary key)")
    await conn.execute_script("TRUNCATE _uow_probe")

    async def insert(_: UnitOfWork) -> None:
        await connections.get("default").execute_query("INSERT INTO _uow_probe (id) VALUES (1)")

    try:
        with pytest.raises(Rollback):
            await _fail_inside_uow(insert)
        _, rows = await conn.execute_query("SELECT count(*) AS n FROM _uow_probe")
        assert rows[0]["n"] == 0
    finally:
        await conn.execute_script("DROP TABLE IF EXISTS _uow_probe")
