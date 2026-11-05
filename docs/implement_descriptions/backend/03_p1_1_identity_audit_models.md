# 03. P1-1 identity·audit 모델과 첫 마이그레이션

- 상태: PR 진행 중
- 관련 PR: #6
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P1 (P1-1)

## 배경
멘토링 1단계의 첫 구현이다. 회원(`users`, `oauth_accounts`)과 감사 로그(`audit_logs`)를 만들고, aerich 마이그레이션 체계와 "실제 마이그레이션으로 만든 DB에서 도는 통합 테스트"를 가동한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `src/app/core/database.py` | 모든 컨텍스트 모델을 단일 Tortoise app `models`에 등록 (decisions B9) |
| `contexts/identity/domain/` | `User`(이메일 소문자, 이름·휴대폰 정규화, 승인 상태 전이 PENDING → APPROVED / REJECTED, REJECTED → APPROVED, 인증 시각 기록), `OAuthAccount`, `UserRepository` Protocol, enum |
| `contexts/identity/infrastructure/` | `UserModel`, `OAuthAccountModel`, `TortoiseUserRepository`(이메일·휴대폰·소셜 계정 조회) |
| `contexts/audit/domain/`, `application/recorder.py` | `AuditLog`(append-only), `AuditLogRepository`(커서 페이지네이션), `AuditRecorder`(다른 컨텍스트가 호출하는 공개 서비스) |
| `contexts/audit/infrastructure/` | `AuditLogModel`(actor는 회원 삭제 시 SET NULL), `TortoiseAuditLogRepository` |
| `migrations/models/0_..._init.py` | aerich 첫 마이그레이션 + raw SQL: DB 기본값(`now()`, `false`, `'PENDING'`), check 제약(이메일 소문자, 승인 상태↔승인 시각, 승인 상태 값, 휴대폰 형식, 소셜 제공자 값) |
| `tests/conftest.py` | `database`: 테스트 DB 스키마를 비우고 aerich 마이그레이션을 처음부터 적용. `db`: 테스트마다 TRUNCATE |
| `tests/factories/identity.py`, `tests/fakes/audit.py` | 회원 빌더, 감사 로그 인메모리 리포지토리 |
| `tests/unit/identity`, `unit/audit`, `integration/identity`, `integration/audit` | 도메인 규칙, 리포지토리 왕복, 유니크·check 제약, DB 기본값, UoW 롤백 시 감사 로그도 롤백 |

## 주요 결정
- **Tortoise 단일 app** (사용자 결정, B9).
  - 컨텍스트별 app으로 실험해 보니 aerich 이력이 app마다 나뉘었다(7개). 다른 app이 참조하는 테이블의 `CREATE TABLE IF NOT EXISTS`가 마이그레이션에 중복으로 들어갔다.
  - 단일 app으로 바꾸면서 코드 경계는 계속 import-linter가 강제한다.
- **P1을 세 PR로 분할** (하네스 규칙): P1-1 identity·audit, P1-2 organization, P1-3 academy
- enum은 varchar로 저장하고 허용 값을 CHECK로 건다. DB 기본값도 raw SQL로 DBML과 맞춘다(앱을 거치지 않는 INSERT 대비).
- `audit_logs.ip`는 Tortoise에 inet 타입이 없어 `varchar(45)`로 두고 DBML을 고쳤다.
- 감사 로그 actor FK는 `ON DELETE SET NULL`이다. 회원은 soft delete이므로 보통은 발생하지 않는다.

## 발견한 문제와 해결
- **aerich 0.10 + Tortoise 1.x:**
  - `aerich.Command`는 Tortoise가 초기화돼 있지 않으면 직접 초기화한다. 그런데 1.x 기본값(전역 연결 없음)으로 초기화하면 연결을 찾지 못한다(`KeyError: 'default'`).
  - 테스트 픽스처에서는 Tortoise를 `_enable_global_fallback=True`로 먼저 초기화한 뒤 `Command.init()` → `upgrade()`를 호출한다.
  - `async with Command(...)`는 `__aenter__`에서 `Migrate.init`을 먼저 실행하므로 이 순서로 쓸 수 없다.
- aerich가 생성한 마이그레이션 파일은 SQL 줄이 길어 ruff E501에 걸린다. `extend-exclude = ["migrations"]`로 린트·포맷 대상에서 뺐다.
- 테스트에서 `tests.factories`를 import하도록 `tests/__init__.py`, pytest `pythonpath`에 `.`, isort first-party에 `tests`를 추가했다. 그러지 않으면 mypy가 같은 파일을 두 모듈 이름으로 인식했다.
- **docker compose의 단일 파일 바인드 마운트 문제:** 호스트에서 `pyproject.toml` 크기가 바뀌자 컨테이너에 잘린 내용이 보였다. 이 PR에서는 컨테이너를 다시 만들어 우회했고, 근본 수정은 별도 fix PR로 한다.

## 검증
- 컨테이너(`docker compose exec api`): ruff, ruff format, mypy(src strict, tests), lint-imports(계약 10개) 통과
- pytest **49개 통과**. 통합 테스트는 aerich 마이그레이션을 적용한 실제 PostgreSQL에서 돌았다. raw SQL check 제약 4종이 위반 시 실패하는 것과 DB 기본값도 확인했다
- GitHub Actions: PR에서 확인 후 기록

## 남은 작업
- P1-2 organization, P1-3 academy (각각 `aerich migrate`로 새 마이그레이션)
- docker compose 단일 파일 마운트 수정 (fix PR)
