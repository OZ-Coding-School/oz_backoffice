# 41. P10-2b 명단 동기화 후 수강 종료 처리

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P10 (P10-2b)
- 이전 기록: [40. P10-2a 멘토링 시간 계좌·지급·조정·조회](40_p10_2a_balance_accounts.md)

## 배경
P10의 마지막 PR이다. 수강생의 수강 상태는 Airtable 명단 동기화(매시간·수동)가 바꾼다(A19). 수강 중이 아니게 된 수강생이 팀에 남거나 1:1 시간을 계속 가지고 있지 않도록, 동기화가 끝난 뒤 정리한다(A39).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/application/enrollment_ended.py` | `EnrollmentEndedService.process`: 팀에서 빼기 + 1:1 잔여 회수, 시스템 감사 로그 |
| `mentoring/domain/balance.py` | `BalanceAccount.revoke_remaining`: 잔여 전부를 STAFF_ADJUST(−)로 회수(60분 단위·사용 기간과 무관). 보류 시간은 그대로 |
| `mentoring/infrastructure/repositories.py` | 팀 소속 전체 조회·일괄 제거, 잔여가 남은 1:1 계좌 조회 |
| `workers/tasks/mentoring.py` | `mentoring.enrollment_ended.process` 작업 |
| `workers/tasks/roster.py` | 명단 동기화(수동 `execute`·매시간 `scheduled`)가 **성공하면** 위 작업을 보낸다 |

**처리 대상:** 수강 중이 아닌 수강생이다. 수강 상태가 ENROLLED가 아니거나(수료·조기취업·중도포기·기수 이동), Airtable 원천에서 삭제됐거나, 명단에서 사라진 경우다. 이들을
- 모든 팀에서 빼고(`mentoring.team.member_auto_remove`),
- 1:1 계좌에 잔여가 있으면 전부 회수한다(사유 "수강 종료로 회수", `mentoring.balance.auto_revoke`).

## 주요 결정 (사용자 결정, A39)
- **처리 시점:** 명단 동기화 직후 작업으로 처리한다. 동기화와 따로 실패·재시도된다.
- **회수 대상:** 팀원만이 아니라 수강 중이 아니게 된 모든 수강생이다.
- **회수 범위:** 잔여 시간이다. 대기 신청 취소와 보류 시간 회수는 신청 기능이 생기는 P11에서 붙인다.
- **복구:** 다시 수강 중이 돼도 자동으로 복구하지 않는다(운영진이 다시 지급·팀 배정).

## 구현 세부
- **멱등:** 이미 뺀 팀원과 잔여가 0인 계좌는 다시 대상이 되지 않는다. 같은 동기화 결과로 여러 번 실행해도 결과가 같다.
- **한 트랜잭션:** 회수할 계좌는 id 순서로 잠근다. 잠그는 사이 잔여가 0이 된 계좌는 건너뛴다.
- **조회 범위:** 전체 팀 소속과 잔여가 남은 1:1 계좌만 읽고, 수강생 상태는 academy `StudentQueries`로 한 번에 묶어 조회한다.
- **회수 단위:** 회수는 운영진 조정(60분 단위)과 달리 잔여 전부다. 신청(P11)의 30분 단위 사용으로 60분 배수가 아닐 수 있기 때문이다.

## 검증
- 단위:
  - 처리: 수강 중·중도포기·원천 삭제·명단에서 사라짐·기수 이동 수강생 → 팀원 3명 제외, 계좌 2개 240분 회수, 잔여 0 계좌 제외
  - 원장 사유, 시스템 감사 로그, 두 번째 실행은 0건
  - `revoke_remaining`: 보류 유지, 60분 단위 아님, 잔여 0이면 없음
- 통합(PostgreSQL):
  - 실제 지급 → 수강 상태 변경 → 처리: 팀원 제외, 계좌 회수, 원장 2줄, 멱등
  - 작업 이름, 동기화 성공일 때만 작업을 보냄(실패면 보내지 않음)
- 전체 679 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 워커 재시작 후 작업 모듈 로드 확인
- 코드 커밋 2개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했다(678 → 679 passed)
- 스키마 변경 없음

## 남은 작업
- P11: 수강 종료 시 대기 신청 취소·보류 시간 회수, HOLD·RELEASE·USING·REFUND
