import uuid
from datetime import date, datetime
from typing import Protocol

from app.contexts.mentoring.domain.artifact import MentoringArtifact
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.availability import Interval
from app.contexts.mentoring.domain.balance import BalanceAccount, BalanceTransaction
from app.contexts.mentoring.domain.enums import MentoringRequestStatus
from app.contexts.mentoring.domain.note import MentoringSessionNote
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.schedule import MentorUnavailablePeriod
from app.contexts.mentoring.domain.session import MentoringSession, SessionQuery
from app.contexts.mentoring.domain.settings import (
    CohortMentoringSettings,
    MentoringBlockTime,
    MentoringHoliday,
)
from app.contexts.mentoring.domain.settlement import MentoringSettlement
from app.contexts.mentoring.domain.team import MentoringTeam


class CohortMentoringSettingsRepository(Protocol):
    async def get_by_cohort(self, cohort_id: uuid.UUID) -> CohortMentoringSettings | None: ...
    async def lock_by_cohort(self, cohort_id: uuid.UUID) -> CohortMentoringSettings | None:
        """설정 행을 잠그고 읽는다 (팀 번호 매기기 등 기수 단위 직렬화)."""
        ...

    async def add(self, settings: CohortMentoringSettings) -> None: ...
    async def save(self, settings: CohortMentoringSettings) -> None: ...


class MentoringBlockTimeRepository(Protocol):
    async def add(self, block: MentoringBlockTime) -> None: ...
    async def save(self, block: MentoringBlockTime) -> None: ...
    async def get(self, block_id: uuid.UUID) -> MentoringBlockTime | None: ...
    async def delete(self, block_id: uuid.UUID) -> None: ...
    async def list_by_cohort(self, cohort_id: uuid.UUID) -> list[MentoringBlockTime]:
        """기간 시작일 순."""
        ...


class MentoringHolidayRepository(Protocol):
    async def add(self, holiday: MentoringHoliday) -> None: ...
    async def get(self, holiday_id: uuid.UUID) -> MentoringHoliday | None: ...
    async def get_by_date(self, day: date) -> MentoringHoliday | None: ...
    async def delete(self, holiday_id: uuid.UUID) -> None: ...
    async def list_between(self, start: date, end: date) -> list[MentoringHoliday]: ...


class CohortMentorRepository(Protocol):
    async def add(self, assignment: CohortMentor) -> None: ...
    async def save(self, assignment: CohortMentor) -> None: ...
    async def get(self, assignment_id: uuid.UUID) -> CohortMentor | None: ...
    async def list_by_ids(self, assignment_ids: list[uuid.UUID]) -> list[CohortMentor]: ...
    async def find_active(
        self, mentor_id: uuid.UUID, cohort_id: uuid.UUID
    ) -> CohortMentor | None: ...
    async def list_by_cohort(
        self, cohort_id: uuid.UUID, *, include_inactive: bool
    ) -> list[CohortMentor]: ...
    async def list_by_mentor(
        self, mentor_id: uuid.UUID, *, include_inactive: bool
    ) -> list[CohortMentor]: ...
    async def list_expired(self, today: date) -> list[CohortMentor]:
        """활성이면서 종료일이 오늘 전인 배정."""
        ...


class MentorUnavailablePeriodRepository(Protocol):
    async def add(self, period: MentorUnavailablePeriod) -> None: ...
    async def save(self, period: MentorUnavailablePeriod) -> None: ...
    async def get(self, period_id: uuid.UUID) -> MentorUnavailablePeriod | None: ...
    async def delete(self, period_id: uuid.UUID) -> None: ...
    async def list_by_mentor(self, mentor_id: uuid.UUID) -> list[MentorUnavailablePeriod]:
        """시작 시각 순 (일회성·반복 모두)."""
        ...


class MentoringTeamRepository(Protocol):
    async def add(self, team: MentoringTeam) -> None: ...
    async def save(self, team: MentoringTeam) -> None:
        """팀과 팀원(추가·제거)을 함께 저장한다."""
        ...

    async def get(self, team_id: uuid.UUID) -> MentoringTeam | None: ...
    async def delete(self, team_id: uuid.UUID) -> None:
        """팀원과 함께 지운다. 계좌·신청이 참조하면 409 `in_use`."""
        ...

    async def list_by_cohort(self, cohort_id: uuid.UUID) -> list[MentoringTeam]:
        """팀 번호 순."""
        ...

    async def next_number(self, cohort_id: uuid.UUID) -> int: ...
    async def team_of_students(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
        """수강생 → 소속 팀."""
        ...

    async def list_by_students(self, student_ids: list[uuid.UUID]) -> list[MentoringTeam]: ...
    async def list_by_ids(self, team_ids: list[uuid.UUID]) -> list[MentoringTeam]: ...
    async def list_memberships(self) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """모든 (팀, 수강생) 소속."""
        ...

    async def remove_memberships(self, pairs: list[tuple[uuid.UUID, uuid.UUID]]) -> None: ...
    async def list_by_mentor(self, mentor_id: uuid.UUID) -> list[MentoringTeam]: ...


class BalanceAccountRepository(Protocol):
    async def add(self, account: BalanceAccount) -> None: ...
    async def save(self, account: BalanceAccount) -> None: ...
    async def get(self, account_id: uuid.UUID) -> BalanceAccount | None: ...
    async def lock_many(self, account_ids: list[uuid.UUID]) -> list[BalanceAccount]:
        """행을 id 순서로 잠그고 읽는다 (SELECT … FOR UPDATE, 교착 방지)."""
        ...

    async def find_by_owners(
        self,
        *,
        student_ids: list[uuid.UUID],
        team_ids: list[uuid.UUID],
    ) -> list[BalanceAccount]: ...
    async def list_student_accounts_with_remaining(self) -> list[BalanceAccount]:
        """잔여가 남은 1:1 계좌 (수강 종료 회수 대상 후보)."""
        ...

    async def list_page(
        self,
        cohort_id: uuid.UUID,
        *,
        owner: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[BalanceAccount], int]:
        """기수의 계좌 (수강생·팀 소유, owner = STUDENT | TEAM | None)."""
        ...


class BalanceTransactionRepository(Protocol):
    async def add_many(self, entries: list[BalanceTransaction]) -> None: ...
    async def list_by_account(
        self, account_id: uuid.UUID, *, before: uuid.UUID | None, limit: int
    ) -> list[BalanceTransaction]:
        """최신순 (id = uuid7 커서)."""
        ...


class MentoringRequestRepository(Protocol):
    async def add(self, request: MentoringRequest) -> None: ...
    async def save(self, request: MentoringRequest) -> None: ...
    async def get(self, request_id: uuid.UUID) -> MentoringRequest | None: ...
    async def lock(self, request_id: uuid.UUID) -> MentoringRequest | None: ...
    async def get_many(self, request_ids: list[uuid.UUID]) -> dict[uuid.UUID, MentoringRequest]: ...
    async def count_pending(
        self, *, requester_id: uuid.UUID | None = None, team_id: uuid.UUID | None = None
    ) -> int:
        """1:1은 그 수강생의 대기 신청 수, 팀은 그 팀의 대기 신청 수."""
        ...

    async def list_for_participants(
        self,
        *,
        student_ids: list[uuid.UUID],
        team_ids: list[uuid.UUID],
        status: MentoringRequestStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MentoringRequest], int]:
        """본인 1:1 신청과 소속 팀 신청 (최신순)."""
        ...

    async def list_for_mentor(
        self,
        mentor_id: uuid.UUID,
        *,
        status: MentoringRequestStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MentoringRequest], int]: ...
    async def list_by_cohort(
        self,
        cohort_id: uuid.UUID,
        *,
        status: MentoringRequestStatus | None,
        mentor_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MentoringRequest], int]: ...
    async def list_stale(self, now: datetime) -> list[MentoringRequest]:
        """대기 중이고 희망 일시가 모두 지난 신청."""
        ...

    async def list_pending(
        self,
        *,
        mentor_id: uuid.UUID | None = None,
        cohort_id: uuid.UUID | None = None,
        team_ids: list[uuid.UUID] | None = None,
        requester_ids: list[uuid.UUID] | None = None,
        solo: bool | None = None,
    ) -> list[MentoringRequest]:
        """조건을 모두 만족하는 대기 신청 (id 순). cohort_id는 신청자의 기수, solo=True는 1:1만."""
        ...


class MentoringSessionRepository(Protocol):
    async def add(self, session: MentoringSession) -> None:
        """멘토 일정이 겹치면(취소 제외, DB EXCLUDE) ConflictError(mentor_schedule_conflict)."""
        ...

    async def get(self, session_id: uuid.UUID) -> MentoringSession | None: ...
    async def save(self, session: MentoringSession) -> None: ...
    async def lock(self, session_id: uuid.UUID) -> MentoringSession | None: ...
    async def get_by_space(self, space_name: str) -> MentoringSession | None: ...
    async def list_needing_space(self, after: datetime) -> list[MentoringSession]:
        """시작 전(after 이후) 예정 세션 중 Meet 공간이 없는 것 (시작 순)."""
        ...

    async def list_recent_with_space(
        self, since: datetime, until: datetime
    ) -> list[MentoringSession]:
        """Meet 공간이 있고 since~until에 끝난(예정 종료) 취소되지 않은 세션 (녹화 보완 수집)."""
        ...

    async def list_needing_close(self) -> list[MentoringSession]:
        """취소됐는데 Meet 링크가 남은 세션."""
        ...

    async def get_by_request(self, request_id: uuid.UUID) -> MentoringSession | None: ...
    async def lock_by_request(self, request_id: uuid.UUID) -> MentoringSession | None: ...
    async def busy(
        self,
        mentor_id: uuid.UUID,
        start: datetime,
        end: datetime,
        *,
        exclude_request_id: uuid.UUID | None = None,
    ) -> list[Interval]:
        """그 멘토의 취소되지 않은 세션 중 [start, end)와 겹치는 구간 (변경 중인 신청은 뺀다)."""
        ...

    async def list_upcoming(
        self,
        after: datetime,
        *,
        mentor_id: uuid.UUID | None = None,
        solo: bool | None = None,
    ) -> list[MentoringSession]:
        """시작 시각이 after보다 늦은 예정(SCHEDULED) 세션 (시작 순). solo=True는 1:1만."""
        ...

    async def count_for_pair(
        self, mentor_id: uuid.UUID, *, requester_id: uuid.UUID | None, team_id: uuid.UUID | None
    ) -> int:
        """같은 멘토·같은 신청자(1:1은 수강생, 팀은 팀)의 취소되지 않은 세션 수 (회차 번호)."""
        ...

    async def has_participant_overlap(
        self,
        *,
        student_ids: list[uuid.UUID],
        team_ids: list[uuid.UUID],
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        """그 수강생들의 1:1 세션이나 그 팀들의 세션 중 시간이 겹치는 것이 있는지 (취소 제외)."""
        ...

    async def list_for_participants(
        self, *, student_ids: list[uuid.UUID], team_ids: list[uuid.UUID], query: SessionQuery
    ) -> tuple[list[MentoringSession], int]: ...
    async def list_for_mentor(
        self, mentor_id: uuid.UUID, query: SessionQuery
    ) -> tuple[list[MentoringSession], int]: ...
    async def list_by_cohort(
        self, cohort_id: uuid.UUID, *, mentor_id: uuid.UUID | None, query: SessionQuery
    ) -> tuple[list[MentoringSession], int]: ...
    async def list_settleable(
        self, cohort_id: uuid.UUID, *, before: datetime
    ) -> list[MentoringSession]:
        """기록된(완료·노쇼) 세션 중 예정 시작이 before 이전인 것 (정산 집계 대상 후보)."""
        ...

    async def list_unrecorded(
        self,
        cohort_id: uuid.UUID,
        *,
        before: datetime,
        limit: int,
        offset: int,
        mentor_id: uuid.UUID | None = None,
    ) -> tuple[list[MentoringSession], int]:
        """예정 시작이 before 이전인데 기록이 없는 세션(예정·진행 중), 시작 오래된 순."""
        ...


class MentoringSessionNoteRepository(Protocol):
    async def get_by_session(self, session_id: uuid.UUID) -> MentoringSessionNote | None: ...
    async def add(self, note: MentoringSessionNote) -> None: ...
    async def save(self, note: MentoringSessionNote) -> None: ...


class MentoringArtifactRepository(Protocol):
    async def add_if_absent(self, artifact: MentoringArtifact) -> bool:
        """(세션, Drive 파일) 유니크. 이미 있으면 False (중복 수신·재수집에 안전)."""
        ...

    async def get(self, artifact_id: uuid.UUID) -> MentoringArtifact | None: ...
    async def save(self, artifact: MentoringArtifact) -> None: ...
    async def list_by_session(self, session_id: uuid.UUID) -> list[MentoringArtifact]: ...
    async def list_pending(self) -> list[MentoringArtifact]: ...


class MentoringSettlementRepository(Protocol):
    async def get(self, settlement_id: uuid.UUID) -> MentoringSettlement | None:
        """명세 포함."""
        ...

    async def get_by_key(
        self, mentor_id: uuid.UUID, cohort_id: uuid.UUID, month: date
    ) -> MentoringSettlement | None: ...
    async def save(self, settlement: MentoringSettlement) -> None:
        """없으면 만들고, 있으면 합계를 고치고 명세를 통째로 바꾼다."""
        ...

    async def list_by_cohort(
        self, cohort_id: uuid.UUID, *, month: date | None
    ) -> list[MentoringSettlement]:
        """명세 없이 (목록용)."""
        ...

    async def settled_session_ids(
        self, session_ids: list[uuid.UUID], *, exclude_settlement_id: uuid.UUID | None
    ) -> set[uuid.UUID]:
        """이미 다른 정산 명세에 들어간 세션."""
        ...
