# Backend

OZ 통합 백오피스 백엔드. 기존 `prev_tools/` 서비스들의 데이터를 PostgreSQL 하나로 통합하고 `apps/frontend`에 REST API를 제공한다.

## 기술 스택

| 영역 | 기술 | 용도 |
| --- | --- | --- |
| 웹 프레임워크 | FastAPI | 비동기 REST API, OpenAPI 문서 자동 생성 |
| ORM | Tortoise ORM | 비동기 ORM, 모델 정의 및 쿼리 |
| 데이터베이스 | PostgreSQL | 주 데이터 저장소 |
| DB 드라이버 | asyncpg | Tortoise ORM의 PostgreSQL 비동기 드라이버 |
| 캐시/세션 | Redis | 캐시, 리프레시 토큰/세션 저장, 레이트 리밋, 분산 락 |
| 인증 | Google OAuth2 | Google 계정 로그인 |
| 토큰 | PyJWT | 액세스/리프레시 JWT 발급 및 검증 |
| 린트/포맷 | ruff | 린트와 코드 포맷팅 |
| 타입 검사 | mypy | 정적 타입 검사 |

## 테스트

| 영역 | 기술 | 용도 |
| --- | --- | --- |
| 비동기 테스트 | pytest + pytest-asyncio | async 엔드포인트/서비스 테스트 |
| Redis 모킹 | fakeredis | 실제 Redis 없이 Redis 동작 검증 |
| HTTP 모킹 | respx | Google OAuth 등 외부 HTTP(httpx) 호출 모킹 |
| 커버리지 | coverage | 테스트 커버리지 측정 |

## 추가 도구

| 영역 | 기술 | 용도 |
| --- | --- | --- |
| 패키지 관리 | uv | 의존성, lock, Python 3.13 |
| 마이그레이션 | aerich | Tortoise 마이그레이션 (EXCLUDE·부분 유니크 등은 생성된 파일에 raw SQL 추가) |
| 작업 큐 | taskiq + taskiq-redis | 백그라운드 작업, cron 스케줄 |
| 의존 규칙 | import-linter | 계층/컨텍스트 간 import 규칙 강제 (`pyproject.toml [tool.importlinter]`) |

## 명령어

### 실행: docker compose (기본)

루트 `docker-compose.yml`이 PostgreSQL 17, Redis 7, 백엔드 `api` / `worker` / `scheduler`를 함께 띄운다. **명령은 저장소 루트에서 실행한다.**

```bash
cp apps/backend/.env.example apps/backend/.env   # 최초 1회 (없어도 기본값으로 뜸)
docker compose up -d --build              # 전체 실행 → API http://localhost:8000/docs
docker compose ps                         # 상태 (api는 /health 헬스체크)
docker compose logs -f api                # 로그
docker compose down                       # 중지 (DB 데이터는 postgres-data 볼륨에 유지)
docker compose down -v                    # 중지 + DB 데이터 삭제 (init SQL이 다시 실행됨)
```

| 서비스 | 내용 |
| --- | --- |
| `api` | `Dockerfile`의 `dev` 타깃. `src`, `tests`, `migrations`, `pyproject.toml`을 마운트하고 `uvicorn --reload`로 실행 → 코드 변경 시 자동 재시작 |
| `worker` / `scheduler` | `api`가 빌드한 이미지를 재사용해 taskiq 실행 (빌드는 `api`만 한다 — 같은 태그 동시 빌드 충돌 방지). **자동 재시작하지 않는다** → 태스크 코드 변경 후 `docker compose restart worker scheduler` |
| `postgres` / `redis` | 호스트에도 5432 / 6379로 노출 (DB 클라이언트, 로컬 uv 실행용) |
| `s3` | S3 에뮬레이터 floci 2.4.0 (`localhost:4566`). 인증 강제(`FLOCI_SERVICES_S3_ENFORCE_AUTH=true`)라 서명 없는 요청·위조 서명은 403. 데이터는 `s3-data` 볼륨에 유지. 선정 근거: `docs/research/local_s3_emulator.md` |
| `s3-init` | `amazon/aws-cli`로 버킷(`oz-backoffice-local`) 생성 + CORS 설정 후 종료 (`infra/s3/init.sh`, `cors.json`, 멱등). 백엔드 서비스는 이 작업이 성공해야 뜬다 |

- 의존성(`pyproject.toml`, `uv.lock`)을 바꾸면 이미지를 다시 만든다: `docker compose up -d --build`
- 컨테이너는 `apps/backend/.env`를 읽되, `DATABASE_URL` / `REDIS_URL` / `TASKIQ_REDIS_URL` / `TEST_DATABASE_URL`과 S3 설정(`AWS_*`, `S3_BUCKET`, `S3_ENDPOINT_URL`)은 compose가 서비스 이름(`postgres`, `redis`, `s3`) 주소로 덮어쓴다.
- **S3 엔드포인트는 둘이다.** 서버가 S3를 호출할 때는 `S3_ENDPOINT_URL`(`http://s3:4566`)을 쓴다. 브라우저에 줄 presigned URL은 `S3_PUBLIC_ENDPOINT_URL`(`http://localhost:4566`)로 서명해야 한다. 서명에 Host가 포함되기 때문이다.
- S3 상태 확인: `docker compose run --rm --entrypoint aws s3-init --endpoint-url http://s3:4566 s3 ls s3://oz-backoffice-local --recursive`

### 검사·테스트·마이그레이션 (api 컨테이너 안에서)

```bash
docker compose exec api pytest                         # 전체 테스트 (통합 테스트까지 실행됨)
docker compose exec api coverage run -m pytest
docker compose exec api coverage report
docker compose exec api ruff check .
docker compose exec api ruff format --check .
docker compose exec api mypy
docker compose exec api mypy tests
docker compose exec api lint-imports

docker compose exec api aerich init-db                 # 최초 1회 (첫 모델 추가 후)
docker compose exec api aerich migrate --name <설명>    # 모델 변경 → migrations/에 생성 (호스트에 반영됨)
docker compose exec api aerich upgrade                 # 적용
```

포맷 자동 수정(`ruff format .`, `ruff check --fix .`)도 컨테이너에서 실행하면 마운트된 호스트 파일이 바뀐다.

### 로컬 실행: uv (IDE·디버거용 대안)

인프라만 compose로 띄우고 백엔드는 호스트에서 실행할 수도 있다. `apps/backend`에서 실행한다.

```bash
docker compose up -d postgres redis       # 루트에서
uv sync
uv run uvicorn app.main:app --reload      # compose의 api와 포트(8000)가 겹치므로 api를 멈추거나 --port 변경
uv run pytest                             # TEST_DATABASE_URL이 없으면 통합 테스트는 skip
TEST_DATABASE_URL=postgres://oz:oz@localhost:5432/oz_backoffice_test uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run mypy tests && uv run lint-imports
```

변경 후에는 ruff, mypy, lint-imports, pytest(통합 테스트 포함)를 모두 통과시킨다.

## 구조 규칙

설계 문서: `docs/implement_plans/backend_architecture.md`, 스키마: `docs/database_schema_v2.dbml`

```text
src/app/
├── main.py          # create_app, lifespan (Tortoise·Redis)
├── core/            # 설정, DB 설정, Redis, UnitOfWork, JWT, 예외 핸들러, Clock
├── shared/          # 공유 커널 (순수 Python): Entity/AggregateRoot, 값 객체, 도메인 예외, 이벤트, uuid7, KST
├── integrations/    # 외부 API 어댑터 (Google — httpx, respx로 테스트 / S3 — aioboto3, floci로 통합 테스트)
├── contexts/<ctx>/  # identity, access, organization, academy, educator, mentoring, audit
│   ├── domain/          # 엔티티·규칙·리포지토리 Protocol (프레임워크 import 금지)
│   ├── application/     # 서비스(유스케이스), 트랜잭션 경계
│   ├── infrastructure/  # Tortoise 모델, 리포지토리 구현, Redis 어댑터
│   └── presentation/    # 라우터, 요청/응답 스키마, 의존성 조립
├── api/             # health, v1 라우터 통합
└── workers/         # taskiq 브로커/스케줄러, 태스크 (서비스 호출 래퍼)
```

- 의존 방향: `presentation → (application | infrastructure) → domain`. 도메인은 `fastapi`, `tortoise`, `redis`, `httpx`, `app.core`를 import하지 않는다.
- 다른 컨텍스트는 `application`(공개 서비스)으로만 호출한다. 다른 컨텍스트의 `infrastructure`/`presentation` import 금지. 예외로 `access.presentation`의 권한 의존성은 공개한다.
- 트랜잭션은 서비스에서 `UnitOfWork`로 연다. 외부 API 호출은 `uow.on_commit(...)`으로 커밋 후에 실행한다.
- 도메인은 시각을 직접 읽지 않고 `now`를 인자로 받는다. 서비스가 `Clock`에서 꺼내 넘긴다.
- 예외는 `app.shared.errors`의 `AppError` 하위 클래스로 던진다. HTTP 매핑은 `app.core.errors`가 한다 (`{"error": {"code", "message"}}`).
- Tortoise 모델은 컨텍스트별 app으로 등록된다 (`app.core.database.MODEL_MODULES`). 다른 컨텍스트 FK는 `"academy.Cohort"`처럼 app 이름을 붙인다. enum은 `CharEnumField`(varchar).
- 테스트: `tests/unit`(DB 없음, `tests/fakes` 인메모리 리포지토리), `tests/integration`(실제 PostgreSQL), `tests/api`(AsyncClient + 의존성 오버라이드). 마커 `unit` / `integration` / `api`.

---

# 작업 하네스

백엔드 작업을 할 때 따르는 절차와 기준이다. 구조 규칙(위)은 import-linter가 강제하고, 여기 적힌 나머지는 이 문서와 리뷰가 지킨다.

## 1. 작업 시작 전

1. **결정 확인:** `docs/decisions.md`에서 관련 항목(멘토링이면 M1~M25)을 읽는다. 결정과 다르게 구현해야 할 것 같으면 구현하지 말고 먼저 묻는다.
2. **스키마 확인:** `docs/database_schema_v2.dbml`에서 대상 테이블의 컬럼, 제약(check, unique), note에 적힌 raw SQL 제약을 확인한다.
3. **원본 동작 확인:** 기존 서비스를 이전하는 작업이면 `docs/analysis/<서비스>.md`와 `prev_tools/<서비스>/`의 원본 코드·테스트를 읽는다. (둘 다 `.gitignore` 대상이라 로컬에만 있다. 없으면 사용자에게 알린다)
4. **기존 코드 확인:** 같은 컨텍스트의 기존 엔티티·리포지토리·서비스 패턴을 먼저 읽고 맞춘다. 새 패턴을 도입해야 하면 이유를 설명하고 확인받는다.
5. **브랜치 확인:** `develop`에서 만든 작업 브랜치인지 확인한다. (`main`·`develop` 직접 커밋 금지, README 참고)
6. 요구사항이나 규칙이 모호하면 **질문으로 하나씩** 확인한다. 추측으로 채우지 않는다.

## 2. 구현 순서 (안쪽에서 바깥쪽으로)

기능 하나(유스케이스 하나)를 아래 순서로 만든다. 단계마다 해당 테스트를 먼저 쓰거나 함께 쓴다.

| 순서 | 계층 | 만드는 것 | 테스트 |
| --- | --- | --- | --- |
| 1 | domain | 엔티티·값 객체·상태 전이·규칙, 도메인 예외, 리포지토리 Protocol | `tests/unit` — 규칙과 경계값, 허용되지 않는 전이 |
| 2 | infrastructure | Tortoise 모델, 마이그레이션(raw SQL 제약 포함), 리포지토리 구현, 매퍼 | `tests/integration` — 저장/조회 왕복, **DB 제약이 실제로 막는지** |
| 3 | application | 서비스(유스케이스), UoW, 컨텍스트 간 호출, 감사 로그 | `tests/unit` — `tests/fakes` 리포지토리 + `FixedClock` |
| 4 | presentation | 라우터, 요청/응답 스키마, 권한 의존성, 의존성 조립 | `tests/api` — 성공, 검증 실패, 401/403, 도메인 예외 매핑 |
| 5 | 문서 | 새 결정은 `docs/decisions.md`, 스키마 변경은 DBML, 완료 시 구현 기록 | — |

## 3. 코드 작성 유의사항

### 공통
- **타입:** mypy strict를 통과해야 한다. `Any`는 외부 경계(JSON 페이로드 등)에서만 쓰고 곧바로 타입 있는 객체로 바꾼다. `# type: ignore`는 오류 코드를 붙이고(`[arg-type]`) 이유를 주석으로 남긴다.
- **비동기:** 이벤트 루프를 막는 코드를 쓰지 않는다. `requests`, `time.sleep`, 동기 파일·네트워크 I/O 금지. 무거운 CPU 작업은 taskiq 워커로 보낸다.
- **시각:** 항상 tz-aware UTC로 다룬다. `datetime.now()` 직접 호출 금지(서비스는 `Clock`, 도메인은 인자). 업무 날짜는 `app.shared.time.business_date`.
- **시간·금액:** 분과 원은 정수(int)로 다룬다. float 금지.
- **ID:** 새 엔티티 ID는 `app.shared.ids.new_id()`(uuid7). 외부 숫자 ID는 문자열.
- **예외:** `AppError` 하위 클래스로 던지고 `code`를 snake_case로 붙인다(`insufficient_balance`). 메시지는 사용자에게 보여줄 수 있는 한국어 문장. 내장 예외(`ValueError` 등)를 계층 밖으로 흘리지 않는다.
- **로깅:** 개인정보(이메일, 전화번호, 생년월일)와 토큰·시크릿을 로그에 남기지 않는다. 식별자는 ID로 남긴다.
- **설정·시크릿:** 환경 값은 `Settings`에만 추가하고 `.env.example`에도 키를 추가한다. 코드에 기본 시크릿을 넣지 않는다.
- **의존성 추가:** `uv add`로만 추가한다. 새 라이브러리는 이유를 설명하고 확인받는다. 기술 선택에 해당하면 `docs/decisions.md` §4에 기록한다.

### 계층별
- **domain:** `@dataclass(kw_only=True, eq=False)` + `Entity`/`AggregateRoot` 상속. 상태 변경은 메서드로만 하고, 메서드 안에서 불변식을 검증한다. 외부에서 필드를 직접 바꾸지 않는다. 의미 있는 상태 변경은 `record(DomainEvent)`로 남긴다.
- **application:** 메서드 하나가 유스케이스 하나다. 트랜잭션은 `async with uow:`로 열고, 외부 API·알림·캐시 무효화는 `uow.on_commit`으로 미룬다. 리소스 단위 권한(내 기수의 수강생인지 등)은 서비스에서 검사한다. 재시도될 수 있는 작업(웹훅, 워커)은 멱등하게 만든다(유니크 키 + 이미 처리된 경우 무시).
- **infrastructure:** 비즈니스 규칙을 두지 않는다. 리포지토리는 애그리거트 루트 단위로만 만들고, 하위 엔티티는 루트와 함께 저장한다. 엔티티를 반환하고 Tortoise 모델을 밖으로 내보내지 않는다.
- **presentation:** 라우터는 검증 → 서비스 호출 → 응답 변환만 한다. 응답은 항상 `response_model`로 명시한다. 역할마다 보여줄 필드가 다르면 스키마를 나눈다(예: 내부 메모는 수강생 응답에 없음). 목록 API는 페이지네이션이 필수다.
- **마이그레이션:** 이미 적용된(커밋된) 마이그레이션 파일은 고치지 않고 새 마이그레이션을 만든다. DBML에 note로 적힌 raw SQL 제약(EXCLUDE, 부분 유니크, 복합 FK)은 마이그레이션에 넣고 통합 테스트로 확인한다. 스키마를 바꾸면 DBML도 같은 커밋에서 고친다.

## 4. 성능 기준

| 항목 | 기준 |
| --- | --- |
| N+1 쿼리 | 목록 조회는 `prefetch_related`/`select_related`나 IN 쿼리로 묶는다. 루프 안에서 쿼리를 날리지 않는다 |
| 쿼리 확인 | 새 조회 경로는 로거 `tortoise.db_client`를 DEBUG로 켜서 실행 쿼리 수를 확인한다. 복잡한 쿼리는 `EXPLAIN ANALYZE`로 인덱스 사용을 확인한다 |
| 인덱스 | 새 WHERE/ORDER BY 조건은 인덱스가 받쳐야 한다. 없으면 DBML과 마이그레이션에 함께 추가한다 |
| 페이지네이션 | 목록은 `limit` 최대 100. 계속 쌓이는 데이터(채팅 메시지, 원장, 감사 로그)는 offset 대신 커서(uuid7 / created_at) 기반으로 한다 |
| 트랜잭션 | 짧게 유지한다. 트랜잭션 안에서 외부 API를 호출하지 않는다. `select_for_update`는 애그리거트 루트에만 쓰고, 여러 행을 잠글 때는 순서를 고정한다(예: 계좌 → 신청 → 세션)로 교착을 막는다 |
| 트랜잭션 안 동시 쿼리 | UoW 안에서는 연결이 하나다. `asyncio.gather`로 쿼리를 동시에 실행하지 않는다 (트랜잭션 밖의 독립 조회는 가능) |
| 대량 처리 | 행 단위 루프 저장 대신 `bulk_create` / `bulk_update` / 단일 UPDATE를 쓴다. 대량 작업은 taskiq로 보낸다 |
| 캐시 | 읽기가 많고 변경이 드문 데이터에만 Redis 캐시를 쓴다. 키는 `oz:<컨텍스트>:<대상>:<id>`, TTL 필수, 쓰기 시 `on_commit`에서 무효화한다. 정합성이 중요한 값(잔여 시간, 정산)은 캐시하지 않는다 |
| 응답 시간 | API 핸들러 p95 300ms 이내를 목표로 한다. 넘을 작업(외부 API 연쇄, 집계)은 비동기 작업으로 돌리고 상태 조회 API를 둔다 |
| 대용량 전송 | Drive 녹화 중계 등은 스트리밍(`StreamingResponse`, Range)으로 처리하고 파일 전체를 메모리에 올리지 않는다 |

## 5. 테스트 기준

- 버그를 고치면 그 버그를 재현하는 테스트를 먼저 추가한다.
- 도메인 규칙은 경계값(0, 잔여 시간과 정확히 같은 값, 기간 시작·종료일)과 허용되지 않는 상태 전이를 모두 테스트한다.
- DB 제약(check, unique, EXCLUDE)은 통합 테스트에서 **위반 시 실제로 실패하는지** 확인한다.
- API 테스트는 역할별 권한(허용 역할 200, 비허용 403, 비로그인 401)을 포함한다.
- 외부 HTTP는 respx로 고정하고, 실제 네트워크를 호출하는 테스트를 만들지 않는다. 시각은 `FixedClock`으로 고정한다.
- 커버리지: domain·application은 변경한 코드의 분기 커버리지 90% 이상을 목표로 한다. 숫자보다 규칙 누락이 없는지가 우선이다.
- 테스트 데이터는 `tests/factories`의 빌더로 만든다. 같은 셋업이 두 번 이상 나오면 빌더나 픽스처로 옮긴다.

## 6. 커밋 단위

- **커밋 하나 = 논리적 변경 하나.** 커밋마다 ruff, mypy, lint-imports, pytest가 통과하는 상태여야 한다. (중간 커밋도 깨지지 않게)
- 코드와 그 코드의 테스트는 같은 커밋에 넣는다.
- 모델 변경, 마이그레이션, DBML 수정은 같은 커밋에 넣는다.
- 기능 변경과 리팩터링, 포맷 변경을 섞지 않는다. 리팩터링이 필요하면 먼저 `refactor:` 커밋으로 분리한다.
- 결정이 생긴 변경이면 `docs/decisions.md` 수정을 그 커밋에 포함한다.
- 크기 기준: 생성 파일(uv.lock, 자동 생성 마이그레이션)을 빼고 300줄 안팎. 넘으면 계층(도메인 → 인프라 → 서비스 → API) 단위로 나눈다.
- 메시지: `<타입>: <한글 설명>` (README, `.github/commit_template.txt`). 본문에 무엇을, 왜.

예) "멘토링 신청" 기능 브랜치의 커밋 흐름
```text
feat: 멘토링 신청 도메인 규칙과 잔여 시간 보류 추가        # domain + unit 테스트
feat: 멘토링 신청·시간 계좌 모델과 마이그레이션 추가       # models + migration + DBML + integration 테스트
feat: 멘토링 신청 서비스 추가                           # application + unit 테스트(fakes)
feat: 멘토링 신청 API 추가                              # presentation + api 테스트
docs: 멘토링 신청 구현 기록 추가                         # implement_descriptions (같은 PR)
```

## 7. PR 단위

- **PR 하나 = 사용자가 확인할 수 있는 기능 하나(수직 슬라이스).** 도메인부터 API까지 한 유스케이스 묶음을 한 PR에 담는다. API 없이 모델만 있는 PR은 공통 기반(마스터 데이터, 인증)일 때만 허용한다.
- 크기 기준: 생성 파일을 빼고 변경 600줄 안팎. 넘으면 유스케이스 단위로 PR을 나눈다.
- 마이그레이션은 PR 하나에 하나를 원칙으로 한다. 기존 데이터에 영향을 주는 마이그레이션은 PR 본문 "참고 사항"에 적용 순서와 되돌리는 방법을 적는다.
- 리팩터링·의존성 업데이트·설정 변경은 기능 PR과 분리한다.
- 구현 기록(`docs/implement_descriptions/backend/NN_*.md`)과 계획 문서 체크리스트 갱신은 같은 PR에 넣는다.
- PR 전에 최신 `develop`으로 rebase하고 전체 검사(통합 테스트 포함)를 다시 돌린다.

### 멘토링 1단계 PR 순서
PR 순서와 PR별 범위(테이블, API, 규칙, 테스트, 선행 준비물)는 **`docs/implement_plans/mentoring_phase1_backend.md`** 를 따른다. (P1 마스터 모델 → P2 인증·운영진 로그인 → P3 권한 → P4 조직·과정·기수 API → P5 Airtable 명단 동기화 → P6 S3 + 계약 → P7 수강생·멘토 가입 → P8 설정·배정 → P9 멘토 일정 → P10 팀·시간 계좌 → P11 신청·승인·취소 → P12 Meet → P13 기록·녹화 → P14 정산 → P15 채팅)
PR을 시작할 때 해당 절과 🔒 선행 준비물을 먼저 확인하고, 끝나면 그 문서의 진행 체크리스트를 갱신한다.

## 8. 완료 기준 (Definition of Done)

- [ ] `ruff check .`, `ruff format --check .` (compose: `docker compose exec api ...`, 로컬: `uv run ...`)
- [ ] `mypy`, `mypy tests`
- [ ] `lint-imports`
- [ ] `pytest` — 통합 테스트까지 실제로 실행 (`docker compose exec api pytest` 또는 `TEST_DATABASE_URL=... uv run pytest`). 못 했으면 못 했다고 보고한다
- [ ] 새 쿼리 경로의 쿼리 수와 인덱스 확인
- [ ] 스키마 변경 시 DBML · 모델 · 마이그레이션 일치
- [ ] 새 결정은 `docs/decisions.md`, 완료 시 구현 기록과 계획 체크리스트 갱신
- [ ] 결과 보고에 실행한 검사와 실행하지 못한 검사를 구분해서 적는다

## 9. 하지 말 것

- 결정(`docs/decisions.md`)과 다른 구현을 확인 없이 진행하기
- 실패하는 테스트를 건너뛰기(`skip`)·삭제·기대값 완화로 통과시키기
- import-linter 계약에 `ignore_imports`를 추가해 위반을 덮기 (정말 필요하면 이유와 함께 확인받기)
- 커밋된 마이그레이션 수정, 운영 데이터에 영향을 주는 명령(`aerich downgrade`, DROP) 확인 없이 실행
- `main`·`develop`에 직접 커밋·push, 강제 push(본인 작업 브랜치의 `--force-with-lease` 제외)
