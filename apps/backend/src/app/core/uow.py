"""Unit of Work: 서비스 계층의 트랜잭션 경계.

Tortoise의 in_transaction은 contextvar로 현재 태스크의 연결을 트랜잭션 연결로 바꾸므로,
블록 안에서 실행되는 모델 쿼리는 모두 같은 트랜잭션에 묶인다.

    async with uow:
        account = await balances.get_for_update(...)
        ...
        uow.on_commit(lambda: meet.create_space(...))   # 커밋 성공 후에만 실행

외부 API 호출은 트랜잭션 안에서 하지 않고 on_commit으로 미룬다.

UoW를 직접 받지 않는 협력 객체(호출한 서비스의 트랜잭션 안에서 도는 자동 정리 등)는
`after_commit(...)`으로 현재 열린 UoW의 커밋 후 작업을 등록한다(contextvar, decisions A58).
열린 UoW가 없으면 바로 실행한다.
"""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar, Token
from types import TracebackType
from typing import Self

from tortoise.backends.base.client import TransactionContext
from tortoise.transactions import in_transaction

AfterCommit = Callable[[], Awaitable[None]]

_current: "ContextVar[UnitOfWork | None]" = ContextVar("oz_current_uow", default=None)


async def after_commit(callback: AfterCommit) -> None:
    """현재 열린 UoW가 있으면 커밋 후로 미루고, 없으면 바로 실행한다."""
    uow = _current.get()
    if uow is None:
        await callback()
    else:
        uow.on_commit(callback)


class UnitOfWork:
    def __init__(self, connection_name: str = "default") -> None:
        self._connection_name = connection_name
        self._tx: TransactionContext | None = None
        self._after_commit: list[AfterCommit] = []
        self._scope: Token[UnitOfWork | None] | None = None

    def on_commit(self, callback: AfterCommit) -> None:
        self._after_commit.append(callback)

    async def __aenter__(self) -> Self:
        if self._tx is not None:
            raise RuntimeError("UnitOfWork는 중첩해서 열 수 없습니다.")
        self._after_commit = []
        self._tx = in_transaction(self._connection_name)
        await self._tx.__aenter__()
        self._enter_scope()
        return self

    def _enter_scope(self) -> None:
        self._scope = _current.set(self)

    def _exit_scope(self) -> None:
        if self._scope is not None:
            _current.reset(self._scope)
            self._scope = None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        tx, self._tx = self._tx, None
        if tx is None:
            raise RuntimeError("열리지 않은 UnitOfWork를 닫으려고 했습니다.")
        self._exit_scope()
        await tx.__aexit__(exc_type, exc, tb)
        if exc_type is None:
            callbacks, self._after_commit = self._after_commit, []
            for callback in callbacks:
                await callback()
