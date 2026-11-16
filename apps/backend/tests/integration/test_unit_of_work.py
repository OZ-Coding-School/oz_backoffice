from collections.abc import Awaitable, Callable

import pytest
from tortoise import connections

from app.core.uow import UnitOfWork, after_commit

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


async def test_after_commit_uses_the_open_uow() -> None:
    """UoW를 받지 않은 코드도 현재 트랜잭션의 커밋 후 작업을 등록한다 (A58)."""
    calls: list[str] = []

    async def note(label: str) -> None:
        calls.append(label)

    await after_commit(lambda: note("no-uow"))  # 열린 UoW가 없으면 바로
    assert calls == ["no-uow"]

    async with UnitOfWork():
        await after_commit(lambda: note("committed"))
        assert calls == ["no-uow"]
    assert calls == ["no-uow", "committed"]

    async def register(_: UnitOfWork) -> None:
        await after_commit(lambda: note("rolled-back"))

    with pytest.raises(Rollback):
        await _fail_inside_uow(register)
    await after_commit(lambda: note("after"))  # 닫힌 뒤에는 다시 바로 실행
    assert calls == ["no-uow", "committed", "after"]


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


async def test_savepoint_rolls_back_only_its_block() -> None:
    conn = connections.get("default")
    await conn.execute_script("CREATE TABLE IF NOT EXISTS _uow_probe (id int primary key)")
    await conn.execute_script("TRUNCATE _uow_probe")
    async with UnitOfWork() as uow:
        await connections.get("default").execute_query("INSERT INTO _uow_probe VALUES (1)")

        async def failing_block() -> None:
            async with uow.savepoint():
                await connections.get("default").execute_query("INSERT INTO _uow_probe VALUES (2)")
                raise Rollback

        with pytest.raises(Rollback):
            await failing_block()
        async with uow.savepoint():
            await connections.get("default").execute_query("INSERT INTO _uow_probe VALUES (3)")
    _, rows = await conn.execute_query("SELECT id FROM _uow_probe ORDER BY id")
    assert [r["id"] for r in rows] == [1, 3]
    await conn.execute_script("DROP TABLE _uow_probe")
