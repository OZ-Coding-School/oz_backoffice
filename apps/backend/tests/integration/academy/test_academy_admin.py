from datetime import date

import pytest

from app.contexts.academy.application.academy_admin import AcademyAdminService
from app.contexts.academy.domain.entities import HrdNetBootcamp, HrdNetBootcampCohort
from app.contexts.academy.domain.enums import CohortStatus, HRDNetTrainType
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseHrdNetBootcampCohortRepository,
    TortoiseHrdNetBootcampRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.identity.domain.entities import User
from app.core.clock import SystemClock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError
from app.shared.ids import new_id
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.integration

D1, D2 = date(2026, 11, 1), date(2027, 4, 30)


def service() -> AcademyAdminService:
    return AcademyAdminService(
        hrd_bootcamps=TortoiseHrdNetBootcampRepository(),
        hrd_cohorts=TortoiseHrdNetBootcampCohortRepository(),
        bootcamps=TortoiseBootcampRepository(),
        cohorts=TortoiseCohortRepository(),
        audit=AuditRecorder(TortoiseAuditLogRepository(), SystemClock()),
        uow=UnitOfWork(),
    )


@pytest.fixture
async def actor() -> User:
    return await create_applicant()


async def _hrd_with_cohort(
    svc: AcademyAdminService, actor: User, suffix: str = "A"
) -> tuple[HrdNetBootcamp, HrdNetBootcampCohort]:
    hrd = await svc.create_hrd_bootcamp(
        {"name": f"HRD {suffix}", "hrd_net_id": f"AIG-{suffix}", "train_type": HRDNetTrainType.KDT},
        actor_id=actor.id,
    )
    hrd_cohort = await svc.create_hrd_cohort(hrd.id, {"cohort_number": 1}, actor_id=actor.id)
    return hrd, hrd_cohort


async def test_full_hierarchy_and_audit(actor: User) -> None:
    svc = service()
    hrd, hrd_cohort = await _hrd_with_cohort(svc, actor)
    bootcamp = await svc.create_bootcamp(
        {"hrd_net_bootcamp_id": hrd.id, "name": "백엔드", "code": "ah"}, actor_id=actor.id
    )
    assert bootcamp.code == "AH"
    cohort = await svc.create_cohort(
        bootcamp.id,
        {"hrd_net_cohort_id": hrd_cohort.id, "cohort_number": 3, "start_date": D1, "end_date": D2},
        actor_id=actor.id,
    )

    updated = await svc.update_cohort(
        cohort.id, {"status": CohortStatus.ONGOING, "discord_guild_id": "123"}, actor_id=actor.id
    )
    assert (updated.status, updated.discord_guild_id) == (CohortStatus.ONGOING, "123")
    assert [c.id for c in await svc.list_cohorts(bootcamp.id)] == [cohort.id]
    log = await AuditLogModel.filter(target_id=cohort.id, action="academy.cohort.update").first()
    assert log is not None
    assert (log.before["status"], log.after["status"]) == ("PLANNED", "ONGOING")  # type: ignore[index]
    assert log.after["start_date"] == "2026-11-01"  # type: ignore[index]

    deactivated = await svc.update_bootcamp(bootcamp.id, {"is_active": False}, actor_id=actor.id)
    assert not deactivated.is_active
    assert await svc.list_bootcamps(include_inactive=False) == []
    assert [b.id for b in await svc.list_bootcamps(include_inactive=True)] == [bootcamp.id]


async def test_cohort_rules(actor: User) -> None:
    svc = service()
    hrd, hrd_cohort = await _hrd_with_cohort(svc, actor, "A")
    other_hrd, other_hrd_cohort = await _hrd_with_cohort(svc, actor, "B")
    bootcamp = await svc.create_bootcamp(
        {"hrd_net_bootcamp_id": hrd.id, "name": "백엔드", "code": "AH"}, actor_id=actor.id
    )
    values = {
        "hrd_net_cohort_id": hrd_cohort.id,
        "cohort_number": 1,
        "start_date": D1,
        "end_date": D2,
    }
    cohort = await svc.create_cohort(bootcamp.id, values, actor_id=actor.id)

    with pytest.raises(ConflictError) as duplicate:
        await svc.create_cohort(bootcamp.id, values, actor_id=actor.id)
    assert duplicate.value.code == "cohort_number_taken"
    with pytest.raises(BusinessRuleViolation) as period:
        await svc.create_cohort(
            bootcamp.id,
            {**values, "cohort_number": 2, "start_date": D2, "end_date": D1},
            actor_id=actor.id,
        )
    assert period.value.code == "invalid_cohort"
    with pytest.raises(BusinessRuleViolation) as mismatch:
        await svc.create_cohort(
            bootcamp.id,
            {**values, "cohort_number": 2, "hrd_net_cohort_id": other_hrd_cohort.id},
            actor_id=actor.id,
        )
    assert mismatch.value.code == "hrd_cohort_mismatch"
    with pytest.raises(BusinessRuleViolation):
        await svc.update_cohort(
            cohort.id, {"hrd_net_cohort_id": other_hrd_cohort.id}, actor_id=actor.id
        )
    with pytest.raises(BusinessRuleViolation):
        await svc.update_cohort(cohort.id, {"end_date": date(2026, 1, 1)}, actor_id=actor.id)
    with pytest.raises(BusinessRuleViolation) as fixed:
        await svc.update_cohort(cohort.id, {"bootcamp_id": new_id()}, actor_id=actor.id)
    assert fixed.value.code == "field_not_updatable"
    assert other_hrd.id != hrd.id


async def test_uniqueness_and_delete_guards(actor: User) -> None:
    svc = service()
    hrd, hrd_cohort = await _hrd_with_cohort(svc, actor)
    with pytest.raises(ConflictError):
        await svc.create_hrd_bootcamp({"name": "중복", "hrd_net_id": "AIG-A"}, actor_id=actor.id)
    with pytest.raises(ConflictError):
        await svc.create_hrd_cohort(hrd.id, {"cohort_number": 1}, actor_id=actor.id)
    bootcamp = await svc.create_bootcamp(
        {"hrd_net_bootcamp_id": hrd.id, "name": "백엔드", "code": "AH"}, actor_id=actor.id
    )
    for dup, code in (
        ({"name": "백엔드", "code": "AL"}, "bootcamp_name_taken"),
        ({"name": "프론트", "code": "ah"}, "bootcamp_code_taken"),
    ):
        with pytest.raises(ConflictError) as exc:
            await svc.create_bootcamp({"hrd_net_bootcamp_id": hrd.id, **dup}, actor_id=actor.id)
        assert exc.value.code == code

    with pytest.raises(ConflictError) as in_use:
        await svc.delete_hrd_bootcamp(hrd.id, actor_id=actor.id)
    assert in_use.value.code == "in_use"
    await svc.delete_bootcamp(bootcamp.id, actor_id=actor.id)
    await svc.delete_hrd_cohort(hrd_cohort.id, actor_id=actor.id)
    await svc.delete_hrd_bootcamp(hrd.id, actor_id=actor.id)
    with pytest.raises(NotFoundError):
        await svc.get_hrd_bootcamp(hrd.id)
