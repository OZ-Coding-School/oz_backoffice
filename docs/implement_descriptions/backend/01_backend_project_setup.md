# 01. 백엔드 프로젝트 세팅과 CI

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 계획: `docs/implement_plans/backend_architecture.md`
- 다음 기록: [02. docker compose 로컬 개발 환경과 S3 에뮬레이터](02_local_docker_compose_and_s3.md)

## 배경
멘토링 기능 이전을 시작하기 전에, 설계 문서의 DDD + 레이어드 구조로 `apps/backend` 뼈대를 만든다. 도구 설정, 테스트 인프라, CI가 동작하는지 확인한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `apps/backend/pyproject.toml`, `uv.lock`, `.python-version` | 의존성(uv, Python 3.13), ruff / mypy(strict) / pytest / coverage / aerich / import-linter 설정 |
| `src/app/main.py` | `create_app(settings)`. lifespan에서 `RegisterTortoise`로 DB, `app.state.redis`로 Redis 연결. CORS, 예외 핸들러, 라우터 등록 |
| `src/app/core/config.py` | pydantic-settings. DB, Redis, taskiq Redis, JWT, Google OAuth, AWS S3(리전, 자격 증명, 버킷, 서버용·브라우저용 엔드포인트, presigned TTL), 업무 타임존 |
| `src/app/core/database.py` | 컨텍스트별 Tortoise app 등록(`MODEL_MODULES`), aerich용 `TORTOISE_ORM` |
| `src/app/core/uow.py` | `UnitOfWork`: `in_transaction` 래핑, 중첩 금지, `on_commit` 콜백은 커밋 성공 후에만 실행 |
| `src/app/core/security.py` | `JWTService`(access/refresh, typ·exp 검증), argon2 비밀번호 해시 |
| `src/app/core/errors.py` | `AppError` → HTTP 상태 매핑, `{"error": {"code", "message"}}` 응답, 미처리 예외 500 |
| `src/app/core/clock.py` | `Clock` 프로토콜, `SystemClock`, 테스트용 `FixedClock` |
| `src/app/core/redis.py`, `pagination.py`, `logging.py` | Redis 클라이언트/의존성, 페이지 스키마, 로깅 |
| `src/app/shared/` | `domain.py`(Entity, AggregateRoot, DomainEvent), `value_objects.py`(Minutes, DateRange, TimeRange, Email), `errors.py`(도메인 예외), `events.py`(이벤트 디스패처), `ids.py`(uuid7), `time.py`(KST, `business_date`) |
| `src/app/contexts/<7개>/` | identity, access, organization, academy, educator, mentoring, audit 각각 domain / application / infrastructure / presentation 빈 패키지. 모델 모듈(`infrastructure/models`)만 Tortoise 등록용으로 존재 |
| `src/app/api/health.py`, `v1.py` | `/health`(생존), `/health/ready`(DB·Redis, 실패 시 503), `/api/v1` 라우터 통합 지점 |
| `src/app/workers/broker.py` | taskiq `ListQueueBroker` + `TaskiqScheduler`, 워커 시작 시 Tortoise 초기화 |
| `tests/` | `conftest.py`(설정, fakeredis, 앱/클라이언트, 통합 DB 픽스처), unit / api / integration 테스트, `factories/`, `fakes/` |
| `apps/backend/CLAUDE.md` | 기술 스택, 명령어, 구조 규칙, 작업 하네스(코드 작성·성능·테스트·커밋·PR 기준) |
| `.github/workflows/ci.yml` | 이전 프로젝트 CI를 이 프로젝트에 맞게 수정. 변경된 앱만 검사. backend: ruff, mypy(src·tests), lint-imports, PostgreSQL 서비스 컨테이너로 통합 테스트 포함 pytest + coverage. frontend: `package.json`이 생기기 전에는 건너뜀. discord_bot 작업 제거 |

## 주요 결정
- 패키지 관리자 uv, Python 3.13 (사용자 결정, decisions B3). 시스템 기본 3.14 대신 라이브러리 호환성을 위해 3.13을 쓴다.
- 마이그레이션 aerich (사용자 결정, B4)
- 작업 큐 taskiq + taskiq-redis (사용자 결정, B5)
- import-linter 도입 (사용자 결정, B6). 계약 10개:
  - 컨텍스트 내부 계층 `presentation → (application | infrastructure) → domain`
  - 도메인·shared는 `fastapi`, `starlette`, `tortoise`, `redis`, `httpx`, `taskiq`, `app.core`, `app.integrations`를 import하지 않음
  - core / shared / integrations는 컨텍스트를 import하지 않음
  - 컨텍스트별로, 다른 컨텍스트가 그 컨텍스트의 infrastructure / presentation을 import하지 않음 (access는 presentation의 권한 의존성만 공개)
- 세팅 범위는 뼈대 + 동작 확인까지 (사용자 결정). Tortoise 모델과 첫 마이그레이션은 P1에서 한다.
- uuid7(`ids.py`)과 KST 업무 날짜(`time.py`)는 설계 문서와 달리 `shared`에 둔다. 도메인이 `core`를 import할 수 없기 때문이다.
- 통합 테스트 DB 주소(`TEST_DATABASE_URL`)는 `.env`가 아니라 실행 시 환경변수로 넘긴다. conftest가 `.env`를 읽지 않기 때문이다.
- S3 설정 값(`config.py`)은 이 PR에 포함한다. 객체 저장소를 GCS에서 S3로 바꾼 결정(C5~C7)은 다음 기록(02)에서 다룬다.

## 발견한 문제와 해결
- **Tortoise ORM이 1.x(1.1.9)로 설치됨.** API를 직접 확인했다.
  - `Tortoise.init`은 `TortoiseContext`를 돌려준다. 전역 접근이 필요한 곳(워커, 통합 테스트)은 `_enable_global_fallback=True`로 초기화한다. FastAPI는 `tortoise.contrib.fastapi.RegisterTortoise`를 lifespan에서 async context manager로 쓴다(기본값이 global fallback 활성).
  - `in_transaction`은 contextvar로 현재 태스크의 연결을 트랜잭션 연결로 바꾸므로, 블록 안의 모델 쿼리가 같은 트랜잭션에 묶인다. `UnitOfWork`는 이 동작에 기대고 있다.
- 모델이 없는 Tortoise 모듈은 `Module ... has no models` RuntimeWarning을 낸다. pytest 설정에서 이 경고를 무시하도록 했다. 첫 모델이 생기면 해당 컨텍스트부터 사라진다.
- ruff의 `S101`(assert 금지)에 걸린 코드 2곳(`errors.py`, `uow.py`)은 assert 대신 명시적인 분기와 예외로 바꿨다.
- 테스트 파일 이름이 겹쳐도 충돌하지 않도록 pytest를 `--import-mode=importlib`로 실행한다.
- CI의 잡 단위 `if`에서는 `hashFiles()`를 쓸 수 없다. 그래서 `changes` 잡이 `apps/frontend/package.json`이 있는지 확인해 출력으로 넘기도록 했다.
- PostgreSQL 서비스 컨테이너에는 init 스크립트를 마운트할 수 없다. 그래서 `btree_gist` 확장을 CI 단계에서 `psql`로 직접 만든다.

## 검증
- 로컬(uv): `ruff check`, `ruff format --check`, `mypy`(src strict), `mypy tests`, `lint-imports`(계약 10개) 모두 통과
- import-linter가 세 종류의 위반을 잡아내는지 임시 위반 파일로 확인했다: 도메인의 tortoise import, 다른 컨텍스트 infrastructure import, 계층 역방향 import
- 실제 PostgreSQL에서 pytest 22개 통과 (통합 테스트 3개 포함, docker compose 환경). 자세한 내용은 기록 02
- `actionlint .github/workflows/ci.yml`: 통과
- GitHub Actions 실행 결과: PR에서 확인 후 기록

## 남은 작업
- P1: 멘토링 범위 Tortoise 모델 → `aerich init-db`, raw SQL 제약(EXCLUDE, 부분 유니크, 복합 FK) 마이그레이션 → 통합 테스트 픽스처를 `generate_schemas`에서 마이그레이션 적용으로 교체 (`tests/conftest.py` TODO)
- 배포 워크플로(`deploy.yml`): 배포 대상 확정 후
