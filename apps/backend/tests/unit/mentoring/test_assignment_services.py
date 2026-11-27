"""기수 멘토 배정·멘토 활성화 서비스 (인메모리 리포지토리 + 고정 시계)."""

import dataclasses
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.contexts.academy.domain.entities import Cohort
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.mentor_contracts import MentorContractQueries
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.domain.entities import EducatorContract
from app.contexts.educator.domain.enums import ContractStatus
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.assignment_service import CohortMentorService
from app.contexts.mentoring.application.contract_sync import AssignmentContractSync
from app.contexts.mentoring.application.mentor_activation import MentorActivationService
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import (
    CohortMentorDeactivationReason,
    MentoringRequestStatus,
)
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError
from app.shared.ids import new_id
from tests.factories.educator import make_mentor_contract
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.educator import InMemoryContractRepository, InMemoryMentorRepository
from tests.fakes.mentoring import CleanupStores, InMemoryCohortMentorRepository
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 10, 3, 0, tzinfo=UTC)  # 2026-11-10 12:00 KST
ACTOR = new_id()


class Cohorts:
    def __init__(self, *cohorts: Cohort) -> None:
        self.items = {c.id: c for c in cohorts}

    async def get_cohort(self, cohort_id: uuid.UUID) -> Cohort | None:
        return self.items.get(cohort_id)


def _cohort() -> Cohort:
    return Cohort(
        hrd_net_cohort_id=new_id(),
        bootcamp_id=new_id(),
        cohort_number=1,
        start_date=date(2026, 11, 1),
        end_date=date(2027, 4, 30),
    )


def _values(mentor: Mentor, contract: EducatorContract, **overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "mentor_id": mentor.id,
        "contract_id": contract.id,
        "start_date": date(2026, 11, 1),
        "end_date": None,
    }
    values.update(overrides)
    return values


class Harness:
    def __init__(self) -> None:
        self.cohort = _cohort()
        self.other_cohort = _cohort()
        self.mentor = Mentor(user_id=new_id())
        self.mentor_repo = InMemoryMentorRepository(self.mentor)
        self.repo = InMemoryCohortMentorRepository()
        self.audit_logs = InMemoryAuditLogRepository()
        self.clock = FixedClock(NOW)
        audit = AuditRecorder(self.audit_logs, self.clock)
        mentors = MentorQueries(self.mentor_repo)
        self.stores = CleanupStores(audit, self.clock)
        self.contract_repo = InMemoryContractRepository()
        # 기수마다 근거 계약 하나 (A110)
        self.contract = make_mentor_contract(
            self.mentor.id, bootcamp_id=self.cohort.bootcamp_id, cohort_id=self.cohort.id
        )
        self.other_contract = make_mentor_contract(
            self.mentor.id,
            bootcamp_id=self.other_cohort.bootcamp_id,
            cohort_id=self.other_cohort.id,
        )
        self.contract_repo.items = {c.id: c for c in (self.contract, self.other_contract)}
        contracts = MentorContractQueries(self.contract_repo)
        self.sync = AssignmentContractSync(
            assignments=self.repo, cleanup=self.stores.cleanup, audit=audit, clock=self.clock
        )
        self.service = CohortMentorService(
            cleanup=self.stores.cleanup,
            assignments=self.repo,
            mentors=mentors,
            contracts=contracts,
            cohorts=Cohorts(self.cohort, self.other_cohort),
            audit=audit,
            uow=FakeUnitOfWork(),
            clock=self.clock,
        )
        self.activation = MentorActivationService(
            cleanup=self.stores.cleanup,
            mentors=mentors,
            assignments=self.repo,
            contracts=contracts,
            audit=audit,
            uow=FakeUnitOfWork(),
            clock=self.clock,
        )

    async def assign(self, *, other: bool = False, **overrides: Any) -> CohortMentor:
        cohort = self.other_cohort if other else self.cohort
        contract = self.other_contract if other else self.contract
        return await self.service.create(
            cohort.id, _values(self.mentor, contract, **overrides), actor_id=ACTOR
        )

    def put_contract(self, contract: EducatorContract) -> EducatorContract:
        self.contract_repo.items[contract.id] = contract
        return contract


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_create_rules(h: Harness) -> None:
    created = await h.assign()
    assert created.is_active
    assert created.end_date is None
    # 다른 기수는 따로, 같은 기수는 하나만 (A41)
    await h.assign(other=True)
    with pytest.raises(ConflictError) as dup:
        await h.assign()
    assert dup.value.code == "assignment_already_exists"
    # 시작일은 기수 기간 안, 종료일은 기수 기간 밖이어도 된다
    with pytest.raises(BusinessRuleViolation) as outside:
        await h.service.create(
            h.cohort.id,
            _values(h.mentor, h.contract, start_date=date(2026, 10, 31)),
            actor_id=ACTOR,
        )
    assert outside.value.code == "assignment_start_outside_cohort"
    await h.service.deactivate(h.cohort.id, created.id, actor_id=ACTOR)
    later = await h.assign(start_date=date(2027, 4, 30), end_date=date(2027, 8, 31))
    assert later.end_date == date(2027, 8, 31)
    assert [log.action for log in h.audit_logs.logs].count("mentoring.assignment.create") == 3


async def test_create_rejects_missing_or_inactive_mentor(h: Harness) -> None:
    with pytest.raises(NotFoundError):
        await h.service.create(
            h.cohort.id, _values(Mentor(user_id=new_id()), h.contract), actor_id=ACTOR
        )
    with pytest.raises(NotFoundError) as no_cohort:
        await h.service.create(new_id(), _values(h.mentor, h.contract), actor_id=ACTOR)
    assert no_cohort.value.code == "cohort_not_found"
    h.mentor.deactivate()
    await h.mentor_repo.save(h.mentor)
    with pytest.raises(BusinessRuleViolation) as inactive:
        await h.assign()
    assert inactive.value.code == "mentor_inactive"


async def test_update_deactivate_reactivate(h: Harness) -> None:
    created = await h.assign()
    updated = await h.service.update(
        h.cohort.id, created.id, {"end_date": date(2026, 12, 31)}, actor_id=ACTOR
    )
    assert updated.end_date == date(2026, 12, 31)
    with pytest.raises(BusinessRuleViolation):
        await h.service.update(h.cohort.id, created.id, {"mentor_id": new_id()}, actor_id=ACTOR)
    with pytest.raises(NotFoundError):
        await h.service.update(new_id(), created.id, {"end_date": None}, actor_id=ACTOR)

    off, _ = await h.service.deactivate(h.cohort.id, created.id, actor_id=ACTOR)
    assert off.deactivation_reason is CohortMentorDeactivationReason.MANUAL
    replacement = await h.assign()
    with pytest.raises(ConflictError):  # 같은 키의 활성 배정이 있으면 재활성화 불가
        await h.service.reactivate(h.cohort.id, created.id, actor_id=ACTOR)
    await h.service.deactivate(h.cohort.id, replacement.id, actor_id=ACTOR)
    on = await h.service.reactivate(h.cohort.id, created.id, actor_id=ACTOR)
    assert on.is_active
    assert on.deactivated_at is None


async def test_expire_ended_is_idempotent(h: Harness) -> None:
    ended = await h.assign(end_date=date(2026, 11, 9))
    today_end = await h.assign(other=True, end_date=date(2026, 11, 10))
    assert await h.service.expire_ended() == 1
    assert await h.service.expire_ended() == 0
    expired = await h.repo.get(ended.id)
    assert expired is not None
    assert expired.deactivation_reason is CohortMentorDeactivationReason.EXPIRED
    still = await h.repo.get(today_end.id)
    assert still is not None
    assert still.is_active


async def test_list_mine_requires_mentor_profile(h: Harness) -> None:
    await h.assign()
    assert len(await h.service.list_mine(h.mentor.account_id, include_inactive=False)) == 1
    with pytest.raises(NotFoundError) as missing:
        await h.service.list_mine(new_id(), include_inactive=False)
    assert missing.value.code == "mentor_profile_not_found"


async def test_mentor_deactivation_preview_then_confirm(h: Harness) -> None:
    regular = await h.assign()
    project = await h.assign(other=True)

    preview = await h.activation.deactivate(h.mentor.id, confirm=False, actor_id=ACTOR)
    assert not preview.applied
    assert {a.id for a in preview.assignments} == {regular.id, project.id}
    mentor = await h.mentor_repo.get(h.mentor.id)
    assert mentor is not None
    assert mentor.is_active

    done = await h.activation.deactivate(h.mentor.id, confirm=True, actor_id=ACTOR)
    assert done.applied
    assert not done.mentor.is_active
    assert await h.repo.list_by_mentor(h.mentor.id, include_inactive=False) == []
    with pytest.raises(BusinessRuleViolation) as again:
        await h.activation.deactivate(h.mentor.id, confirm=True, actor_id=ACTOR)
    assert again.value.code == "mentor_already_inactive"
    with pytest.raises(BusinessRuleViolation):  # 비활성 멘토는 일괄 재활성화 불가
        await h.activation.reactivate_assignments(h.mentor.id, [regular.id], actor_id=ACTOR)


async def test_mentor_activation_returns_restorable_and_bulk_is_partial(h: Harness) -> None:
    regular = await h.assign()
    project = await h.assign(other=True, end_date=date(2026, 11, 20))
    await h.activation.deactivate(h.mentor.id, confirm=True, actor_id=ACTOR)

    h.clock.set(NOW + timedelta(days=15))  # 2026-11-25: project 배정은 종료일이 지남
    activated = await h.activation.activate(h.mentor.id, actor_id=ACTOR)
    assert activated.mentor.is_active
    assert [a.id for a in activated.restorable] == [regular.id]

    other = new_id()
    result = await h.activation.reactivate_assignments(
        h.mentor.id, [regular.id, project.id, other, regular.id], actor_id=ACTOR
    )
    assert [a.id for a in result.reactivated] == [regular.id]
    assert {(f.assignment_id, f.code) for f in result.failed} == {
        (project.id, "assignment_period_ended"),
        (other, "assignment_not_found"),
    }


async def test_bulk_skips_manual_and_duplicate_keys(h: Harness) -> None:
    first = await h.assign()
    await h.service.deactivate(h.cohort.id, first.id, actor_id=ACTOR)  # MANUAL
    second = await h.assign()
    await h.activation.deactivate(h.mentor.id, confirm=True, actor_id=ACTOR)
    await h.activation.activate(h.mentor.id, actor_id=ACTOR)
    third = await h.assign()  # 복구 전에 새로 배정

    assert await h.activation.restorable(h.mentor.id) == []
    result = await h.activation.reactivate_assignments(
        h.mentor.id, [first.id, second.id, third.id], actor_id=ACTOR
    )
    assert result.reactivated == []
    assert [f.code for f in result.failed] == [
        "assignment_not_restorable",
        "assignment_already_exists",
        "assignment_already_active",
    ]


async def test_deactivations_cancel_pending(h: Harness) -> None:
    here, there = new_id(), new_id()
    h.stores.requests.cohort_of_student = {here: h.cohort.id, there: h.other_cohort.id}
    assignment = await h.assign()
    other = await h.assign(other=True, end_date=date(2026, 11, 9))
    in_cohort = await h.stores.pending(mentor_id=h.mentor.id, requester_id=here)
    elsewhere = await h.stores.pending(mentor_id=h.mentor.id, requester_id=there)

    _, canceled = await h.service.deactivate(h.cohort.id, assignment.id, actor_id=ACTOR)
    assert canceled == 1
    assert h.stores.status(in_cohort) is MentoringRequestStatus.CANCELED
    assert h.stores.status(elsewhere) is MentoringRequestStatus.PENDING

    assert await h.service.expire_ended() == 1  # 만료도 그 기수 대기 신청을 취소
    assert h.stores.status(elsewhere) is MentoringRequestStatus.CANCELED
    assert other.id in {
        a.id for a in await h.repo.list_by_mentor(h.mentor.id, include_inactive=True)
    }


async def test_mentor_deactivation_counts_and_cancels_pending(h: Harness) -> None:
    await h.assign()
    request = await h.stores.pending(mentor_id=h.mentor.id)
    preview = await h.activation.deactivate(h.mentor.id, confirm=False, actor_id=ACTOR)
    assert (preview.applied, preview.pending_requests) == (False, 1)
    assert h.stores.status(request) is MentoringRequestStatus.PENDING
    done = await h.activation.deactivate(h.mentor.id, confirm=True, actor_id=ACTOR)
    assert (done.applied, done.pending_requests) == (True, 1)
    assert h.stores.status(request) is MentoringRequestStatus.CANCELED


async def test_contract_basis_rules(h: Harness) -> None:
    """근거 계약 (A110): 그 멘토의 SIGNED·ACTIVE 멘토 계약, 그 기수 또는 같은 과정 공통, 기간 안."""
    common = h.put_contract(
        make_mentor_contract(
            h.mentor.id,
            bootcamp_id=h.cohort.bootcamp_id,
            start_date=date(2026, 11, 1),
            end_date=date(2027, 1, 31),
        )
    )
    created = await h.assign(contract_id=common.id, end_date=date(2027, 1, 31))
    assert created.contract_id == common.id
    await h.service.deactivate(h.cohort.id, created.id, actor_id=ACTOR)

    cases: list[tuple[EducatorContract, dict[str, Any], str]] = [
        (
            make_mentor_contract(new_id(), bootcamp_id=h.cohort.bootcamp_id),
            {},
            "assignment_contract_mismatch",
        ),
        (
            make_mentor_contract(
                h.mentor.id, bootcamp_id=h.cohort.bootcamp_id, status=ContractStatus.IN_PROGRESS
            ),
            {},
            "assignment_contract_not_effective",
        ),
        (h.other_contract, {}, "assignment_contract_other_cohort"),
        (
            common,
            {"end_date": None, "start_date": date(2027, 2, 1)},
            "assignment_outside_contract_period",
        ),
        (common, {"end_date": date(2027, 2, 28)}, "assignment_outside_contract_period"),
    ]
    for contract, overrides, code in cases:
        h.put_contract(contract)
        with pytest.raises(BusinessRuleViolation) as rule:
            await h.assign(contract_id=contract.id, **overrides)
        assert rule.value.code == code
    with pytest.raises(NotFoundError) as missing:
        await h.assign(contract_id=new_id())
    assert missing.value.code == "contract_not_found"

    candidates = await h.service.contract_candidates(h.cohort.id, h.mentor.id)
    assert {c.id for c in candidates} == {h.contract.id, common.id}


async def test_contract_closed_and_trimmed(h: Harness) -> None:
    """계약이 끝나면 배정을 끄고, 기간이 줄면 배정 기간도 줄인다 (A110)."""
    here = new_id()
    h.stores.requests.cohort_of_student = {here: h.cohort.id}
    long = await h.assign(end_date=None)
    short = await h.assign(other=True, start_date=date(2026, 11, 1))
    request = await h.stores.pending(mentor_id=h.mentor.id, requester_id=here)

    await h.sync.contract_period_changed(
        h.contract.id, start_date=date(2026, 11, 5), end_date=date(2026, 12, 31), actor_id=ACTOR
    )
    trimmed = await h.repo.get(long.id)
    assert trimmed is not None
    assert (trimmed.start_date, trimmed.end_date, trimmed.is_active) == (
        date(2026, 11, 5),
        date(2026, 12, 31),
        True,
    )
    assert await h.sync.has_active_assignments(h.other_contract.id)

    # 남는 기간이 없으면 끈다
    await h.sync.contract_period_changed(
        h.other_contract.id, start_date=None, end_date=date(2026, 10, 31), actor_id=None
    )
    gone = await h.repo.get(short.id)
    assert gone is not None
    assert gone.deactivation_reason is CohortMentorDeactivationReason.CONTRACT_ENDED

    await h.sync.contract_closed(h.contract.id, actor_id=None)
    closed = await h.repo.get(long.id)
    assert closed is not None
    assert closed.deactivation_reason is CohortMentorDeactivationReason.CONTRACT_ENDED
    assert h.stores.status(request) is MentoringRequestStatus.CANCELED
    assert not await h.sync.has_active_assignments(h.contract.id)

    # 끝난 계약의 배정은 다시 켜지 않는다
    h.put_contract(dataclasses.replace(h.contract, status=ContractStatus.ENDED))
    with pytest.raises(BusinessRuleViolation) as ended:
        await h.service.reactivate(h.cohort.id, long.id, actor_id=ACTOR)
    assert ended.value.code == "assignment_contract_not_effective"
