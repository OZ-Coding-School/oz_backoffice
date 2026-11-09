# 21. P5-2b 명단 동기화 동시 실행 락과 taskiq 작업

- 상태: 완료 (2026-11-09 병합)
- 관련 PR: #24
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P5 (P5-2b), §2.5 백그라운드 작업
- 이전 기록: [20. P5-2a Airtable 명단 레코드 해석과 동기화 서비스](20_p5_2a_roster_sync_service.md)

## 배경
P5-2a의 동기화 서비스를 실제로 돌리는 부분이다. Airtable 원천 어댑터, 동시 실행 제어, 수동 실행 작업, 매시 전체 동기화를 만든다. 운영진이 쓰는 API는 P5-2c에서 만든다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `academy/domain/repositories.py` | `RosterSyncLock` Protocol |
| `academy/infrastructure/roster_sync_lock.py` | Redis 락. `oz:lock:roster-sync:all`, `oz:lock:roster-sync:bootcamp:<id>`. 자기 키를 SET NX로 잡은 뒤 충돌 키를 확인하고, 충돌이 있으면 자기 키를 지운다. TTL 30분 |
| `academy/infrastructure/airtable_source.py` | `AirtableRosterSource`: pyairtable 클라이언트로 (레코드 ID, 필드)를 읽는다 |
| `academy/application/roster_sync.py` | `request`(락 → 실행 이력 RUNNING → 실행자 감사 로그, 실패하면 락을 놓음), `run_scheduled`(다른 실행 중이면 건너뜀), `execute`(끝나면 락을 놓음, 이미 끝난 실행이 다시 오면 아무것도 하지 않음) |
| `workers/tasks/roster.py` | `academy.roster_sync.execute(run_id)`, `academy.roster_sync.scheduled`(cron `0 * * * *`, Airtable 설정이 없으면 건너뜀). 서비스를 조립하는 얇은 래퍼 |
| `docker-compose.yml` | worker·scheduler 명령에 작업 모듈 `app.workers.tasks.roster` 추가 |
| `tests/conftest.py` | 테스트 설정의 `AIRTABLE_*`을 비움 |
| `tests/` | 락 규칙(전체 ↔ 과정, 같은 과정, 다른 과정, 실패 시 키가 남지 않음, TTL), 원천 어댑터, 요청·실행·락 해제, 주기 동기화 건너뛰기, 중복 전달 시 새 락 유지, 작업 등록·스케줄·설정 없으면 건너뛰기 |

## 주요 결정
- **락 범위(계획서):** 전체 동기화 중에는 다른 모든 동기화를 막는다. 과정·기수 동기화는 같은 과정끼리만 막는다. 기수 동기화도 과정 단위로 잠근다. 같은 과정의 두 기수를 동시에 돌리면 원천 삭제 판정 범위는 겹치지 않지만, 별칭 수식 조회가 겹쳐 Airtable 호출만 늘기 때문이다.
- **두 단계 잡기:** 각 실행이 자기 키를 먼저 잡고 상대 키를 확인한다. 이렇게 하면 동시에 들어온 두 실행이 둘 다 성공하지 않는다. 둘 다 실패할 수는 있지만 409 후 다시 실행하면 된다. Lua 스크립트 없이 단순하게 유지했다.
- **락은 API가 잡고 워커가 놓는다.** 워커가 죽을 때를 대비해 TTL을 30분으로 둔다(실데이터 366건 동기화는 수 초).
- **중복 전달:** taskiq가 같은 작업을 다시 전달하면 이미 끝난 실행은 처리하지 않고, 같은 범위의 새 실행이 잡은 락도 놓지 않는다.
- **주기 동기화:** 수동 동기화가 돌고 있으면 그 주기를 건너뛴다. 다음 주기에 다시 시도한다.
- **테스트 격리:** compose `env_file`이 실제 Airtable 자격 증명을 컨테이너 환경변수로 넣는다. 그래서 테스트 설정에서 비운다(구현 기록 10의 DEBUG·GOOGLE 문제와 같은 원인).

## 발견한 문제와 해결
- 작업 등록 테스트가 처음에 실패했다. 테스트 설정이 사용자 `.env`의 Airtable 값을 읽어 "설정됨"으로 판정했기 때문이다. 테스트 설정에서 `AIRTABLE_*`을 비웠다.
- 처음 구현에서는 이미 끝난 실행이 다시 전달돼도 `finally`에서 락을 놓았다. 그러면 같은 범위의 새 실행이 잡은 락이 풀릴 수 있었다. 실제로 실행한 경우에만 락을 놓도록 고치고 테스트로 고정했다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **308개 통과**
- 커밋 2개를 각각 워크트리로 꺼내 같은 검사 통과
- GitHub Actions (PR #24, run 42580624254): backend 잡 통과
- 사용자 확인: P5 진행 지시에 따라 CI 통과 후 병합
- **실제 Airtable + 실제 워커 E2E** (개발 DB에 임시 과정 `헬스케어` 별칭과 1~3기를 만들고, 확인 후 삭제)
  - 과정 동기화를 요청해 taskiq로 워커에 보냈고 SUCCEEDED
  - 366건 조회, 1~3기 수강생 160명 생성(1기 59명은 수식으로 센 건수와 일치)
  - DB에 없는 4~8기 206건은 `cohort_not_found`로 실패 목록에 기록
  - 수강 상태: 수료 107, 중도포기 39, 조기취업 14
  - HRD상태 UNKNOWN 8건
  - 휴대폰 140건, 이메일 143건(형식이 틀린 값은 비움)
  - 1기만 다시 동기화: 59건 조회, 변경 0(멱등)

## 남은 작업
- P5-2c: 관리 API(동기화 요청 → 작업 전달, 실행 이력, 기수별 명단, 실패 목록)
- 운영 배포 전에 운영과정마다 `airtable_cohort_prefix`를 설정하고 실제 기수를 등록해야 한다
