# 백엔드 프로젝트 구조 설계

> **상태 (2026-11-05):** 뼈대 구현 완료. 기록은 `docs/implement_descriptions/backend/01_backend_project_setup.md`
> - [x] 도구 설정 (uv, ruff, mypy, pytest, coverage, aerich, import-linter)
> - [x] core / shared 공통 모듈, 7개 컨텍스트 빈 계층 패키지, health API, taskiq 브로커
> - [x] 테스트 인프라 (unit / api / integration 픽스처)
> - [x] 통합 테스트 실제 PostgreSQL 실행 (docker compose)
>
> 기능 구현 계획은 `docs/implement_plans/mentoring_phase1_backend.md`(P1~P15)를 따른다.
> - [ ] 멘토링 범위 Tortoise 모델 + 첫 마이그레이션 (raw SQL 제약 포함)
> - [ ] identity / access (Google 로그인, 권한 의존성)
> - [x] CI 워크플로 (`.github/workflows/ci.yml`, GitHub 실행은 첫 PR에서 확인)
>
> 아래 §3 트리 중 `integrations/` 하위 파일, 컨텍스트의 개별 모듈(entities.py 등), `scripts/seed_roles.py`, `workers/recording_poll.py`는 **아직 만들지 않은 계획**이다.

대상: `apps/backend`
스택: FastAPI, Tortoise ORM(asyncpg), PostgreSQL, Redis, pytest-asyncio (+ fakeredis, respx, coverage), ruff, mypy
스키마 기준: `docs/database_schema_v2.dbml`

---

## 1. 설계 원칙

1. **DDD 바운디드 컨텍스트로 최상위를 나눈다.** 기술 계층(models/, routers/, services/)을 최상위에 두지 않는다. 기능을 고칠 때 한 컨텍스트 폴더 안에서 끝나게 하려는 것이다.
2. **컨텍스트 내부는 4계층이다.**

   | 계층 | 폴더 | 역할 | 요청하신 구성 |
   | --- | --- | --- | --- |
   | 표현 | `presentation/` | HTTP 입출력, 인증·권한 의존성, 요청/응답 스키마 | **router** |
   | 응용 | `application/` | 유스케이스, 트랜잭션 경계, 컨텍스트 간 조율 | **service** |
   | 도메인 | `domain/` | 엔티티, 값 객체, 도메인 규칙, 리포지토리 인터페이스 | (규칙의 위치) |
   | 인프라 | `infrastructure/` | Tortoise 모델, 리포지토리 구현, Redis·외부 API 어댑터 | **repository** |

3. **의존 방향은 `presentation → application → domain ← infrastructure`다.**
   - 도메인은 FastAPI, Tortoise, Redis를 import하지 않는 순수 Python이다.
   - 리포지토리는 도메인에 `Protocol`로 정의하고, 인프라가 구현한다. 서비스는 인터페이스에만 의존한다.
   - 이 규칙은 `import-linter`로 CI에서 강제한다(권장).
4. **Tortoise 모델은 영속성 모델이다.** 도메인 엔티티(dataclass)와 분리하고, 리포지토리가 둘 사이를 변환(mapper)한다.
   - 장점: 잔여 시간 원장이나 신청 상태 전이 같은 규칙을 DB 없이 단위 테스트할 수 있다.
   - 비용: 매핑 코드가 생긴다. 규칙이 거의 없는 단순 CRUD 컨텍스트는 이 비용이 아깝다. 그런 곳(예: 직위)은 서비스가 엔티티 대신 DTO를 다뤄도 된다. 다만 **리포지토리 인터페이스는 반드시 거친다.**
5. **트랜잭션은 서비스 계층에서 Unit of Work로 연다.** 리포지토리는 트랜잭션을 열지 않는다.
6. **컨텍스트 간 호출은 상대 컨텍스트의 공개 서비스(`application/` 파사드)로만 한다.** 다른 컨텍스트의 모델이나 리포지토리를 직접 import하지 않는다. FK는 DB에 걸고, 코드에서는 상대 컨텍스트의 ID로만 참조한다.

---

## 2. 바운디드 컨텍스트

스키마 v2를 기준으로 나눈 컨텍스트다.

| 컨텍스트 | 패키지 | 테이블 | 비고 |
| --- | --- | --- | --- |
| 인증·회원 | `identity` | users, oauth_accounts | Google OAuth, JWT 발급, 리프레시 토큰(Redis) |
| 권한 | `access` | roles, permissions, role_permissions, user_roles | `require_permission` 의존성을 제공 |
| 조직 | `organization` | departments, employee_positions, employees, bootcamp_staffs, cohort_staffs | 담당자 배정 시 `access` 서비스로 user_roles 동기화 |
| 과정·기수 | `academy` | hrd_net_bootcamps, hrd_net_bootcamp_cohorts, bootcamps, cohorts, students | 공통 마스터 |
| 교육 인력 | `educator` | mentors, instructors, educator_contracts, contract_files | 가입 시 계약 이메일로 자동 연결 |
| 멘토링 | `mentoring` | cohort_mentoring_*, cohort_mentors, mentor_availabilities, mentor_unavailable_periods, mentoring_* | 가장 큰 컨텍스트. 내부를 애그리거트 단위로 다시 나눈다 |
| 감사 | `audit` | audit_logs | 다른 컨텍스트가 `AuditRecorder`로 기록 |

### 멘토링 애그리거트

| 애그리거트 | 루트 | 포함 | 핵심 규칙 |
| --- | --- | --- | --- |
| 기수 멘토링 정책 | CohortMentoringSettings | block_times | 진행 시간 단위, 신청 마감, 대기 중 신청 수 |
| 멘토 배정 | CohortMentor | — | ACTIVE 계약 기간 안에서만 배정, 같은 유형 기간 겹침 금지 |
| 멘토 일정 | MentorSchedule | availabilities, unavailable_periods | 희망 일시가 가능 시간 안에 있는지 판정 |
| 시간 계좌 | BalanceAccount | transactions | HOLD / RELEASE / USING / REFUND 전이, 잔여 시간 ≥ 0 |
| 팀 | MentoringTeam | team_members | 유형별 한 팀 소속, 담당 멘토 |
| 신청 | MentoringRequest | — | PENDING → APPROVED / REJECTED / CANCELED, 변경은 취소 후 새 신청 |
| 세션 | MentoringSession | artifacts, note | Meet 이벤트로 상태 전이, 멘토 일정 겹침 금지 |
| 정산 | Settlement | items | DRAFT → CLOSED, 세션은 한 번만 정산 |
| 채팅 | ChatThread | messages, reads | 1:1 또는 팀 |

---

## 3. 디렉터리 구조

```text
apps/backend/
├── CLAUDE.md
├── pyproject.toml              # 의존성 + ruff / mypy / pytest / coverage 설정
├── uv.lock                     # (패키지 관리자: uv 권장)
├── .env.example
├── Dockerfile
├── migrations/                 # aerich 마이그레이션 (EXCLUDE, 부분 유니크 등 raw SQL 포함)
│   └── models/
├── scripts/                    # 시드, 레거시 이관 스크립트
│   └── seed_roles.py
├── src/
│   └── app/
│       ├── main.py             # create_app(), lifespan(Tortoise·Redis 연결/해제), 라우터 등록
│       │
│       ├── core/               # 프레임워크 공통 (모든 컨텍스트가 사용)
│       │   ├── config.py       # pydantic-settings (DB, Redis, JWT, Google, S3)
│       │   ├── database.py     # TORTOISE_ORM 설정 (컨텍스트별 models 모듈 등록)
│       │   ├── redis.py        # Redis 클라이언트 생성/의존성
│       │   ├── uow.py          # UnitOfWork (Tortoise in_transaction 래핑, on_commit)
│       │   ├── security.py     # JWT 인코딩/검증 (PyJWT), argon2 해시
│       │   ├── errors.py       # 예외 핸들러 (shared.errors → HTTP 상태)
│       │   ├── pagination.py   # 오프셋 페이지네이션 스키마
│       │   ├── clock.py        # Clock 프로토콜, SystemClock, FixedClock(테스트)
│       │   └── logging.py
│       │
│       ├── shared/             # 공유 커널 (순수 Python, 도메인이 import 가능)
│       │   ├── domain.py       # Entity / AggregateRoot 베이스, DomainEvent
│       │   ├── value_objects.py  # Minutes, DateRange, TimeRange, Email
│       │   ├── errors.py       # AppError 계층 (NotFound, Conflict, BusinessRuleViolation ...)
│       │   ├── events.py       # 프로세스 내 이벤트 디스패처 (트랜잭션 커밋 후 발행)
│       │   ├── ids.py          # uuid7 생성
│       │   └── time.py         # KST, business_date
│       │
│       ├── integrations/       # 외부 시스템 어댑터 (httpx 기반 → respx로 테스트)
│       │   ├── google/
│       │   │   ├── oauth.py        # 로그인 (Authorization Code + PKCE, ID 토큰 검증)
│       │   │   ├── meet.py         # Space 생성, conferenceRecords 조회
│       │   │   ├── drive.py        # 녹화 파일 메타 조회, Range 스트리밍
│       │   │   └── workspace_events.py  # 이벤트 구독 관리, 수신 페이로드 파싱
│       │   └── s3.py           # aioboto3: presigned POST(업로드)·GET(다운로드), head/delete (프로필, 계약서)
│       │
│       ├── contexts/
│       │   ├── identity/
│       │   │   ├── domain/
│       │   │   │   ├── entities.py       # User, OAuthAccount
│       │   │   │   ├── repositories.py   # UserRepository(Protocol)
│       │   │   │   └── errors.py
│       │   │   ├── application/
│       │   │   │   ├── auth_service.py   # Google 로그인, 토큰 발급/갱신/폐기
│       │   │   │   ├── user_service.py
│       │   │   │   └── dto.py
│       │   │   ├── infrastructure/
│       │   │   │   ├── models.py         # Tortoise: User, OAuthAccount
│       │   │   │   ├── repositories.py   # TortoiseUserRepository
│       │   │   │   └── token_store.py    # Redis 리프레시 토큰 저장소
│       │   │   └── presentation/
│       │   │       ├── router.py         # /auth, /users/me
│       │   │       ├── schemas.py
│       │   │       └── dependencies.py   # get_current_user
│       │   │
│       │   ├── access/         # (identity와 같은 4계층 구조)
│       │   │   └── presentation/dependencies.py  # require_permission("mentoring.request.approve", scope=...)
│       │   ├── organization/
│       │   ├── academy/
│       │   ├── educator/
│       │   ├── audit/
│       │   │   └── application/recorder.py       # AuditRecorder (다른 컨텍스트가 호출)
│       │   │
│       │   └── mentoring/      # 큰 컨텍스트: 계층 안에서 애그리거트별 모듈로 분리
│       │       ├── domain/
│       │       │   ├── enums.py          # RequestStatus, SessionStatus, PeriodType ...
│       │       │   ├── settings.py       # CohortMentoringSettings, BlockTime
│       │       │   ├── assignment.py     # CohortMentor
│       │       │   ├── schedule.py       # MentorSchedule (가능 시간 판정)
│       │       │   ├── balance.py        # BalanceAccount, BalanceTransaction (hold/release/use/refund)
│       │       │   ├── team.py
│       │       │   ├── request.py        # MentoringRequest (상태 전이)
│       │       │   ├── session.py        # MentoringSession, Artifact, SessionNote
│       │       │   ├── settlement.py     # Settlement, SettlementItem (정산 금액 계산)
│       │       │   ├── chat.py
│       │       │   ├── events.py         # RequestApproved, SessionCanceled ...
│       │       │   ├── repositories.py   # 애그리거트별 Repository Protocol
│       │       │   └── errors.py
│       │       ├── application/
│       │       │   ├── settings_service.py
│       │       │   ├── assignment_service.py
│       │       │   ├── schedule_service.py
│       │       │   ├── balance_service.py
│       │       │   ├── team_service.py
│       │       │   ├── request_service.py    # 신청(HOLD) / 승인(세션 생성 + USING + Meet) / 반려(RELEASE) / 취소(RELEASE 또는 REFUND)
│       │       │   ├── session_service.py    # 기록 제출, Meet 이벤트 반영
│       │       │   ├── artifact_service.py   # 녹화 수집, 스트리밍 권한 확인
│       │       │   ├── settlement_service.py
│       │       │   ├── chat_service.py
│       │       │   └── dto.py
│       │       ├── infrastructure/
│       │       │   ├── models/               # Tortoise 모델 (애그리거트별 파일)
│       │       │   │   ├── __init__.py       # Tortoise 등록용 re-export
│       │       │   │   ├── settings.py
│       │       │   │   ├── balance.py
│       │       │   │   ├── request.py
│       │       │   │   ├── session.py
│       │       │   │   └── ...
│       │       │   ├── repositories/
│       │       │   │   ├── balance.py        # select_for_update로 계좌 잠금
│       │       │   │   ├── request.py
│       │       │   │   └── ...
│       │       │   ├── mappers.py            # 모델 ↔ 엔티티
│       │       │   └── chat_pubsub.py        # Redis Pub/Sub (실시간 채팅)
│       │       └── presentation/
│       │           ├── routers/
│       │           │   ├── __init__.py       # mentoring 라우터 묶음
│       │           │   ├── requests.py       # /mentoring/requests
│       │           │   ├── sessions.py
│       │           │   ├── balances.py
│       │           │   ├── teams.py
│       │           │   ├── schedules.py
│       │           │   ├── settlements.py
│       │           │   ├── chat.py           # REST + WebSocket(또는 SSE)
│       │           │   └── (Meet 이벤트는 웹훅이 아니라 Pub/Sub pull 워커가 처리 — decisions M18)
│       │           ├── schemas/
│       │           └── dependencies.py       # 서비스 조립 (리포지토리 구현 주입)
│       │
│       ├── api/
│       │   └── v1.py           # 컨텍스트 라우터 통합 (prefix /api/v1)
│       │
│       └── workers/            # 백그라운드 작업 (작업 큐 선택 후 구현)
│           └── recording_poll.py   # 녹화 보완 폴링 (recording_status + ends_at)
│
└── tests/
    ├── conftest.py             # 이벤트 루프, 설정 오버라이드, Tortoise·Redis 픽스처, AsyncClient
    ├── factories/              # 테스트 데이터 빌더 (user, cohort, student, mentor ...)
    ├── fakes/                  # 인메모리 리포지토리 (서비스 단위 테스트용)
    ├── unit/                   # DB 없음: 도메인 규칙 + 서비스(가짜 리포지토리)
    │   └── contexts/
    │       └── mentoring/
    │           ├── test_balance.py
    │           ├── test_request.py
    │           └── test_request_service.py
    ├── integration/            # 실제 PostgreSQL: 리포지토리, 제약조건(EXCLUDE·check·부분 유니크), 트랜잭션
    │   └── contexts/mentoring/
    └── api/                    # httpx AsyncClient + ASGITransport: 라우터, 인증·권한, 에러 응답
        └── mentoring/
```

---

## 4. 계층별 규칙

### 4.1 presentation (router)
- 라우터는 **요청 스키마 검증 → 서비스 호출 → 응답 스키마 변환**만 한다. 비즈니스 분기는 넣지 않는다.
- 인증·권한은 의존성으로 처리한다. `Depends(get_current_user)`, `Depends(require_permission(...))`
- 역할별로 노출 필드가 다르면 응답 스키마를 나눈다. 예: 내부 메모는 수강생 응답에 아예 포함하지 않는다(`SessionForStudent` / `SessionForMentor`).
- 외부 숫자 ID는 문자열로 직렬화한다.
- (변경 2026-11-05) Workspace Events는 웹훅이 아니라 Pub/Sub pull 구독을 워커가 처리한다 (decisions M18). 앞으로 웹훅을 추가하게 되면, 서명이나 토큰을 검증하고 이벤트를 저장한 뒤 바로 200을 돌려준다. 처리는 워커가 한다.

### 4.2 application (service)
- 유스케이스 하나가 메서드 하나다. 예: `RequestService.approve(request_id, chosen_at, actor)`
- 트랜잭션 경계는 여기다.
  ```python
  async with self.uow:                        # in_transaction
      account = await self.balances.get_for_update(owner, period_type)
      request = await self.requests.get(request_id)
      session = request.approve(chosen_at, now=self.clock.now())   # 도메인 규칙
      account.use(request)                    # HOLD → USING
      await self.sessions.add(session)
      await self.balances.save(account)
      await self.audit.record(actor, "mentoring.request.approve", request.id)
  # 커밋 후: Meet Space 생성 (외부 호출은 트랜잭션 밖에서)
  ```
- **외부 API 호출(Meet, Drive)은 트랜잭션 안에서 하지 않는다.** 커밋 후 실행하고, 실패하면 재시도 대상으로 상태를 남긴다.
- 다른 컨텍스트가 필요하면 그 컨텍스트의 서비스를 주입받는다. 예: 멘토링이 `academy.StudentQueryService`로 수강생의 기수를 확인한다.

### 4.3 domain
- 엔티티는 `@dataclass`(slots)로 만들고, 상태를 바꾸는 메서드가 규칙을 검증한다. 예: `BalanceAccount.hold(minutes)`는 잔여 시간이 부족하면 `InsufficientBalance`를 던진다.
- 시간(`now`)은 인자로 받는다. 도메인이 직접 시계를 읽지 않아야 테스트가 쉬워진다.
- 리포지토리 인터페이스는 애그리거트 루트 단위로만 둔다. 거래 내역이나 아이템 같은 하위 엔티티는 루트를 통해 저장한다.

### 4.4 infrastructure (repository)
- Tortoise 모델은 컨텍스트별 `infrastructure/models`에 둔다. `core/database.py`에서 앱별로 등록한다.
  ```python
  TORTOISE_ORM = {
      "connections": {"default": settings.database_url},
      "apps": {
          # (변경 2026-11-05, decisions B9) 컨텍스트별 app 대신 단일 app에 모든 컨텍스트 모듈을 등록
          "models": {"models": [
              "app.contexts.identity.infrastructure.models",
              # ... 7개 컨텍스트
              "aerich.models",
          ]},
      },
  }
  ```
  컨텍스트 간 FK는 `fields.ForeignKeyField("models.UserModel")`처럼 참조한다. 마이그레이션 이력은 하나다.
- 잠금이 필요한 조회는 `select_for_update()`를 쓴다. 예: 시간 계좌, 정산 마감.
- 도메인 enum은 `CharEnumField`로 저장한다. Tortoise는 PostgreSQL 네이티브 enum을 만들지 않으므로 DB 값은 varchar다. 값 제약이 필요하면 마이그레이션에서 CHECK를 추가한다.
- DBML로 표현하지 못한 제약(EXCLUDE, 부분 유니크, 복합 FK)은 aerich 마이그레이션 파일에 raw SQL로 넣는다. 그리고 `tests/integration`에서 **제약이 실제로 동작하는지** 검증한다.
- Redis 사용처: 리프레시 토큰, 레이트 리밋, 분산 락(작업 중복 실행 방지), 채팅 Pub/Sub. 각각 해당 컨텍스트의 `infrastructure/`에 어댑터로 둔다.

---

## 5. 테스트 전략

| 종류 | 위치 | 대상 | 인프라 |
| --- | --- | --- | --- |
| 단위 | `tests/unit` | 도메인 규칙, 서비스 흐름 | 없음 (`tests/fakes`의 인메모리 리포지토리, 고정 clock) |
| 통합 | `tests/integration` | 리포지토리, DB 제약, 트랜잭션·잠금 | **실제 PostgreSQL** (docker-compose의 테스트 DB). SQLite로는 EXCLUDE, 배열, 부분 인덱스를 검증할 수 없다 |
| API | `tests/api` | 라우터, 인증·권한, 에러 매핑 | 실제 PostgreSQL + fakeredis + respx(Google API) |

- pytest 설정: `asyncio_mode = "auto"`, `--cov=app`, 마커 `unit` / `integration` / `api`
- DB 픽스처: 세션 시작 시 마이그레이션 적용, 테스트마다 트랜잭션 롤백 또는 TRUNCATE로 격리
- Redis 픽스처: `fakeredis.aioredis.FakeRedis`를 의존성 오버라이드로 주입
- 외부 HTTP: `respx.mock`으로 Google OAuth·Meet·Drive 응답을 고정

---

## 6. 결정사항 (2026-11-05)
1. **패키지 관리자:** uv (Python 3.13)
2. **마이그레이션 도구:** aerich. EXCLUDE·부분 유니크·복합 FK는 생성된 마이그레이션 파일에 raw SQL로 추가한다.
3. **작업 큐·스케줄러:** taskiq + taskiq-redis (`app/workers/broker.py`)
4. **실시간 채팅 전송 방식:** 채팅 구현 시점에 결정 (WebSocket / SSE)
5. **의존성 규칙 강제:** import-linter 도입 (`pyproject.toml [tool.importlinter]`, 계약 10개)

### 구현하면서 바뀐 점
- uuid7 생성(`ids.py`)과 KST 업무 날짜(`time.py`)는 `core`가 아니라 `shared`에 둔다. 도메인이 `core`를 import할 수 없기 때문이다.
- 도메인 예외 계층(`AppError` 등)은 `shared/errors.py`, HTTP 매핑은 `core/errors.py`에 있다.
