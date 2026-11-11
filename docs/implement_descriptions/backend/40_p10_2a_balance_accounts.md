# 40. P10-2a 멘토링 시간 계좌·지급·조정·조회

- 상태: PR 진행 중
- 관련 PR: #45
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P10 (P10-2a)
- 이전 기록: [39. P10-1 멘토링 팀 구성](39_p10_1_mentoring_teams.md)

## 배경
P10의 두 번째 PR이다. 운영진이 수강생(1:1)·팀에 멘토링 시간을 지급·조정하고, 계좌별 원장으로 이력을 남긴다. 수강생은 자기 계좌와 원장을 본다. 신청(P11)은 이 계좌에서 시간을 보류·사용·환불한다. 수강 종료 처리(팀에서 빼기·잔여 회수)는 P10-2b로 나눴다(A40).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/balance.py` | `BalanceAccount`: 지급·조정(60분 단위, 사유 필수, 만료 계좌는 차감만, 잔여 음수 불가)·사용 기간 수정(기수 기간 안). `BalanceTransaction`: 원장 한 줄 |
| `mentoring/infrastructure/models/balance.py`, `migrations/models/15_…` | 계좌·원장 + raw SQL(check 9종, 소유자·유형 부분 유니크 2개, 신청·유형 부분 유니크) |
| `mentoring/infrastructure/repositories.py` | 계좌(id 순서 `SELECT … FOR UPDATE`, 소유자별·기수별 조회), 원장(bulk 추가, uuid7 커서), 팀 `list_by_ids` |
| `mentoring/application/balance_service.py` | `BalanceService`: 지급(대상 4종), 조정, 기간 수정, 기수별 계좌·원장, 본인 계좌·원장, 감사 로그 |
| `core/idempotency.py` | `RedisIdempotency`: Idempotency-Key로 같은 요청을 한 번만 처리 |
| `mentoring/presentation/balance_router.py` | API (아래 표) |

| 메서드 | 경로 | 비고 |
| --- | --- | --- |
| GET | `/api/v1/admin/cohorts/{id}/mentoring-balances?period_type=&owner=&limit=&offset=` | 계좌 목록(소유자 이름, 만료 여부) |
| POST | `…/mentoring-balances/grants` | 지급. `Idempotency-Key` 필수. 결과는 `granted`·`skipped`(사유) |
| PATCH | `…/mentoring-balances/{account_id}` | 사용 기간 수정 |
| POST | `…/mentoring-balances/{account_id}/adjustments` | 조정(±). `Idempotency-Key` 필수 |
| GET | `…/mentoring-balances/{account_id}/transactions?before=&limit=` | 원장(최신순, 커서) |
| GET | `/api/v1/me/balances`, `/me/balances/{id}/transactions` | 본인 1:1·소속 팀 계좌와 원장 |

운영진 API의 권한은 `mentoring.balance.grant`(기수 범위, 매니저·조교)다.

## 주요 결정 (사용자 결정, A39·A40)
- **계좌 생성:** 첫 지급 때 만든다. 사용 기간 기본값은 기수 시작일~종료일이고, 기수 기간 안이어야 한다. 이후 지급은 기간을 바꾸지 않고, 기간은 따로 수정한다.
- **만료 계좌:** 지급과 늘리는 조정은 거부하고, 줄이는 조정만 허용한다.
- **단위·사유:** 지급·조정은 60분 단위이고 사유가 필수다(100자).
- **지급 대상:** 기수 전체 수강 중 수강생 / 고른 수강생 / 기수·유형의 모든 팀 / 고른 팀. 분을 비우면 기수 설정의 기본 지급 시간을 쓴다.
- **일괄 지급 실패 처리:** 가능한 대상만 지급하고, 수강 종료·다른 기수·만료·유형 불일치는 사유와 함께 돌려준다.
- **중복 방지:** 요청 ID(Idempotency-Key, 24시간)로 막는다.
- **본인 조회:** 잔여와 원장을 보여 주고, 처리자는 보여 주지 않는다(원장에 저장하지 않음, M25).

## 구현 세부
- **지급 흐름(한 트랜잭션):**
  1. 대상을 정리한다.
  2. 기존 계좌를 id 순서로 잠근다.
  3. 대상마다 지급하고(새 계좌는 생성), 원장을 bulk로 넣는다.
  4. 감사 로그를 한 건 남긴다(지급 분·사유·계좌 목록·건너뛴 수).
- **요청 전체 오류:** 분(60분 단위)·기간·사유·대상 없음은 대상별로 건너뛰지 않고 요청 전체를 거부한다.
- **요청 ID 처리:** 처음 온 요청은 키를 "처리 중"으로 잡고 실행한 뒤 응답을 24시간 보관한다. 같은 키가 다시 오면 저장된 응답을 그대로 준다. 처리 중에 또 오면 409 `request_in_progress`, 실패하면 키를 지워 재시도할 수 있게 한다. 범위는 요청자 + 기수(지급) 또는 계좌(조정)다.
- **원장 FK:** `request_id`의 `mentoring_requests` FK는 신청 테이블이 생기는 P11 마이그레이션에서 건다.
- **잔여 저장:** 잔여(`remaining_minutes`)는 계좌에 저장하고 DB check(잔여 = 합계 − 보류 − 사용)로 일관성을 지킨다.

## 발견한 문제와 해결
- 지급 분이 60분 단위가 아니면 대상마다 건너뛰어 "전원 건너뜀"이 됐다. 요청 단위 검증으로 앞당겼다.
- 요청 ID 의존성이 Redis를 `app.state`에서 직접 꺼내 테스트의 Redis 대체(의존성 오버라이드)를 우회했다. `Depends(get_redis)`로 바꿨다.

## 검증
- 단위:
  - 도메인: 소유자·기간, 지급·조정(잔여와 같은 값까지 차감), 분 단위 4종, 사유 3종, 만료(종료일 당일·다음 날, 차감만), 기간(기수 밖·거꾸로·같은 날)
  - 서비스: 전체 수강생 기본 분·기본 기간, 재지급 시 기간 유지, 건너뛰기 사유 4종, 팀 지급·유형 불일치, 요청 검증, 조정·기간·원장, 본인·팀 계좌
  - 요청 ID: 같은 키 한 번 실행, 범위 분리, 실패 후 재시도, 처리 중 409
- 통합(PostgreSQL):
  - 계좌·원장 왕복, 커서, 소유자별·기수별 조회, (소유자, 유형) 유니크 409, 계좌 check 4종·원장 check 3종
  - **동시 차감 경합**: 잔여 60분에 −60 두 건을 동시 실행하면 한 건만 성공하고 잔여 0
- API:
  - 지급: 요청 ID 누락 422, 같은 ID 재전송 → 같은 응답, 목록, 수강 종료 건너뜀
  - 조정: 차감, 초과 차감 422
  - 기간: 기수 밖 422, 수정
  - 원장: 커서
  - 본인: 계좌·원장, 남의 계좌 404
  - 권한: 401·403, 다른 기수
- 전체 675 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 마이그레이션 왕복: upgrade → migrate("No changes detected") → downgrade -v 15 → upgrade. DBML 검증
- 코드 커밋 3개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했다(665 → 671 → 675 passed)

## 남은 작업
- P10-2b: 명단 동기화 후 수강 종료 처리(팀에서 빼기, 1:1 잔여 회수)
- P11: HOLD·RELEASE·USING·REFUND, 원장 `request_id` FK, 대기 신청 취소와 보류 시간 회수(A39)
