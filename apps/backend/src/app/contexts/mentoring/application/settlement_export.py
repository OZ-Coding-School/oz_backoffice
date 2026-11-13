"""정산 CSV 행 만들기 (decisions A56, P14-2).

기본 열은 항상, 선택 열(`OPTIONAL_COLUMNS`)은 요청한 것만 넣는다. 이름·세션 정보는 묶어서
한 번씩 조회한다.
"""

import uuid
from collections.abc import Iterable, Mapping
from typing import Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.domain.enums import (
    MentoringSettlementPolicy,
    MentoringSettlementStatus,
    PayUnit,
    SettlementItemType,
)
from app.contexts.mentoring.domain.repositories import (
    MentoringRequestRepository,
    MentoringSessionRepository,
    MentoringTeamRepository,
)
from app.contexts.mentoring.domain.settlement import MentoringSettlement
from app.shared.time import KST

BASE_COLUMNS: list[tuple[str, str]] = [
    ("bootcamp", "과정"),
    ("cohort", "기수"),
    ("mentor", "멘토"),
    ("month", "정산 월"),
    ("status", "정산 상태"),
    ("starts_at", "진행 일시"),
    ("requester", "신청자"),
    ("item_type", "유형"),
    ("policy", "정산 기준"),
    ("minutes", "정산 시간(분)"),
    ("pay_unit", "단가 단위"),
    ("pay_rate", "단가(원)"),
    ("amount", "금액(원)"),
    ("session_id", "세션 ID"),
]
OPTIONAL_COLUMNS: dict[str, str] = {
    "topic": "주제",
    "summary": "요약",
    "recorded_minutes": "기록한 진행 시간(분)",
    "meet_started_at": "Meet 실제 시작",
    "meet_ended_at": "Meet 실제 종료",
}
STATUS_LABELS = {
    MentoringSettlementStatus.DRAFT: "집계 중",
    MentoringSettlementStatus.CLOSED: "마감",
}
TYPE_LABELS = {SettlementItemType.SESSION: "진행", SettlementItemType.NO_SHOW: "노쇼"}
POLICY_LABELS = {
    MentoringSettlementPolicy.ACTUAL_DURATION: "실제 진행",
    MentoringSettlementPolicy.STUDENT_REQUEST: "신청 시간",
}
UNIT_LABELS = {PayUnit.HOURLY: "시급", PayUnit.PER_SESSION: "회당"}
TIME_FORMAT = "%Y-%m-%d %H:%M"


class CohortLabelLike(Protocol):
    @property
    def bootcamp_name(self) -> str: ...
    @property
    def cohort_number(self) -> int: ...


class CohortLabels(Protocol):
    async def cohort_labels(
        self, cohort_ids: Iterable[uuid.UUID]
    ) -> Mapping[uuid.UUID, CohortLabelLike]: ...


class StudentLookup(Protocol):
    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]: ...


class MentorLookup(Protocol):
    async def get_many(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, Mentor]: ...


class UserLookup(Protocol):
    async def get_many(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, User]: ...


def header(columns: list[str]) -> list[str]:
    return [label for _, label in BASE_COLUMNS] + [OPTIONAL_COLUMNS[c] for c in columns]


class SettlementExporter:
    def __init__(
        self,
        *,
        sessions: MentoringSessionRepository,
        requests: MentoringRequestRepository,
        teams: MentoringTeamRepository,
        students: StudentLookup,
        mentors: MentorLookup,
        users: UserLookup,
        cohorts: CohortLabels,
    ) -> None:
        self._sessions = sessions
        self._requests = requests
        self._teams = teams
        self._students = students
        self._mentors = mentors
        self._users = users
        self._cohorts = cohorts

    async def rows(
        self, settlements: list[MentoringSettlement], columns: list[str]
    ) -> list[list[str]]:
        """명세 한 줄 = 한 행 (정산서 → 진행 일시 순). 선택 열은 `columns` 순서대로."""
        items = [(s, i) for s in settlements for i in s.items]
        sessions = await self._sessions.get_many([i.session_id for _, i in items])
        requests = await self._requests.get_many([s.request_id for s in sessions.values()])
        students = await self._students.get_many(list({r.requester_id for r in requests.values()}))
        teams = {
            t.id: t
            for t in await self._teams.list_by_ids(
                list({r.team_id for r in requests.values() if r.team_id})
            )
        }
        mentors = await self._mentors.get_many(list({s.mentor_id for s in settlements}))
        users = await self._users.get_many([m.user_id for m in mentors.values()])
        labels = await self._cohorts.cohort_labels({s.cohort_id for s in settlements})

        def mentor_name(mentor_id: uuid.UUID) -> str:
            mentor = mentors.get(mentor_id)
            user = users.get(mentor.user_id) if mentor else None
            return user.name if user else ""

        rows: list[list[str]] = []
        for settlement, item in sorted(
            items,
            key=lambda pair: (
                str(pair[0].mentor_id),
                sessions[pair[1].session_id].starts_at.timestamp()
                if pair[1].session_id in sessions
                else 0,
            ),
        ):
            session = sessions.get(item.session_id)
            request = requests.get(session.request_id) if session else None
            label = labels.get(settlement.cohort_id)
            if request is not None and request.team_id is not None:
                team = teams.get(request.team_id)
                requester = team.label if team else ""
            elif request is not None:
                student = students.get(request.requester_id)
                requester = student.name if student else ""
            else:
                requester = ""
            row = [
                label.bootcamp_name if label else "",
                f"{label.cohort_number}기" if label else "",
                mentor_name(settlement.mentor_id),
                settlement.settlement_month.strftime("%Y-%m"),
                STATUS_LABELS[settlement.status],
                session.starts_at.astimezone(KST).strftime(TIME_FORMAT) if session else "",
                requester,
                TYPE_LABELS[item.item_type],
                POLICY_LABELS[item.settlement_policy],
                str(item.billable_minutes),
                UNIT_LABELS.get(item.pay_unit, item.pay_unit.value),
                str(item.pay_rate),
                str(item.amount),
                str(item.session_id),
            ]
            optional = {
                "topic": session.topic if session else "",
                "summary": (session.body or "") if session else "",
                "recorded_minutes": str(session.record_duration_minutes or "") if session else "",
                "meet_started_at": session.actual_started_at.astimezone(KST).strftime(TIME_FORMAT)
                if session and session.actual_started_at
                else "",
                "meet_ended_at": session.actual_ended_at.astimezone(KST).strftime(TIME_FORMAT)
                if session and session.actual_ended_at
                else "",
            }
            rows.append(row + [optional[c] for c in columns])
        return rows
