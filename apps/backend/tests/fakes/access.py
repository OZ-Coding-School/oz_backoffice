"""access 가짜: 회원별 권한·데이터 범위 (A87)."""

import uuid

from app.contexts.access.application.permissions import NO_GRANT, StaffGrant


class FakeGrantSource:
    """회원 → StaffGrant 고정값. 조회 횟수를 센다."""

    def __init__(self) -> None:
        self.grants: dict[uuid.UUID, StaffGrant] = {}
        self.calls = 0

    async def grant_of(self, user_id: uuid.UUID) -> StaffGrant:
        self.calls += 1
        return self.grants.get(user_id, NO_GRANT)


class FakeCohortDirectory:
    """기수 → 과정 매핑 고정값. 조회 횟수를 센다."""

    def __init__(self, mapping: dict[uuid.UUID, uuid.UUID] | None = None) -> None:
        self.mapping = mapping or {}
        self.lookups = 0

    async def bootcamp_id_of(self, cohort_id: uuid.UUID) -> uuid.UUID | None:
        self.lookups += 1
        return self.mapping.get(cohort_id)
