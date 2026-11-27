# 107. 운영진 팀 목록 집계 (BE-3z2)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A108 (F93)
- 이전 기록: [106. 달력 참고용 휴일 조회 (BE-3z)](106_calendar_holidays.md)

## 배경
FE-19b 팀 관리 목록에 팀마다 팀 계좌 잔여와 신청·세션 수를 보여 준다(사용자 결정: 백엔드 보완 후 표시). 멘티 목록(A59)과 같은 기준으로 팀 건만 센다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `mentoring/domain/repositories.py`, `infrastructure/repositories.py` | `count_pending_by_teams`(팀별 대기 신청 수), `count_by_teams`(팀별 상태별 세션 수) |
| `mentoring/application/team_stats.py` | `TeamStatsQueries`: 팀 계좌·대기 신청·예정/완료 세션 수 |
| `mentoring/presentation/team_router.py` | `GET /admin/cohorts/{id}/mentoring-teams` 응답을 `AdminTeamResponse`(팀 + `account`·`pending_request_count`·`upcoming_session_count`·`completed_session_count`)로 |
| `tests/fakes/mentoring.py`, 테스트 | 가짜 저장소, 저장소 통합 테스트, API 테스트 |

## 검증
- `ruff`, `mypy`(src·tests), `lint-imports`, `pytest`(924개)

## 남은 작업
- FE-19b 팀 관리 화면에서 사용.
