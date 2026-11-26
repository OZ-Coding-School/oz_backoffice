# 106. 달력 참고용 휴일 조회 (BE-3z)

- 상태: PR 진행 중
- 관련 PR: #172
- 관련 결정: `docs/decisions.md` A107 (F89)
- 이전 기록: [105. 운영진 멘토별 세션 조회 (BE-3y)](105_admin_mentor_sessions.md)

## 배경
멘토 일정 화면을 월 달력으로 바꾸면서(F89) 공휴일을 빨강으로 참고 표시한다. 지금 휴일 조회(`GET /admin/mentoring-holidays`)는 멘토링 설정 권한이 있는 운영진만 쓸 수 있어, 멘토도 쓸 수 있는 기간 조회를 더한다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `contexts/mentoring/presentation/settings_router.py` | `calendar_router`(`/mentoring`) — `GET /mentoring/holidays?from=&to=` 로그인한 누구나, `BusinessCalendar.holidays_between`으로 법정공휴일·추가 휴일, 100일 제한 |
| `api/v1.py` | 라우터 등록 |
| `tests/api/test_mentoring_settings.py` | 멘토 조회·기간 검사·비로그인 401 |

## 주요 결정 (사용자 결정, A107)
- 법정공휴일과 추가 휴일을 함께 보여 준다. 추가 휴일은 기수별이 아니라 운영진이 등록하는 전사 공통 휴일이다.
- 참고 표시일 뿐 신청 가능 시간 계산에는 넣지 않는다.

## 검증
- `ruff`, `mypy`(src·tests), `lint-imports`, `pytest`(923개)

## 남은 작업
- 프론트엔드 월 달력(F89, PR #171)에서 사용.
