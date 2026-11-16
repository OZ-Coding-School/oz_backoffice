"""단위 테스트용 UnitOfWork: 트랜잭션 없이 커밋 후 콜백만 실행한다."""

from types import TracebackType
from typing import Self

from app.core.uow import UnitOfWork


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        super().__init__()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> Self:
        self._after_commit = []
        self._enter_scope()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._exit_scope()
        if exc_type is not None:
            self.rollbacks += 1
            return
        self.commits += 1
        callbacks, self._after_commit = self._after_commit, []
        for callback in callbacks:
            await callback()
