# 10. P3-1 역할·권한 모델과 최고 관리자 CLI

- 상태: PR 진행 중
- 관련 PR: (작성 예정)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P3 (P3-1)
- 이전 기록: [09. P2-2 운영진 최초 정보 입력](09_p2_2_staff_registration.md)

## 배경
P2가 끝나서 운영진이 로그인하고 신청할 수 있게 됐다. 하지만 승인할 관리자가 없다. 사용자 요청은 두 가지였다. "이메일을 입력하면 최고 관리자로 등록되는 CLI script"를 만들고, 부서·직위는 시드 없이 테스트용 임의 데이터로 확인하라는 것이다. CLI가 SUPER_ADMIN을 저장하려면 역할 테이블이 필요하다. 그래서 P3의 역할·권한 모델과 함께 만든다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `contexts/access/domain/catalog.py` | plan §2.3 권한표를 코드로 정의 (권한 12개, 역할 5개와 허용 범위). 시드의 단일 출처 |
| `contexts/access/domain/entities.py` | `UserRole`: 역할 존재, 범위 대상 유무(GLOBAL만 대상 없음), 역할별 허용 범위, 만료. 조회용 `RoleGrant` |
| `contexts/access/infrastructure/` | 모델 3개 + M2M through `role_permissions`. 카탈로그 동기화(멱등, 정의에서 빠진 매핑 정리), 역할 부여·존재 확인·유효 역할 조회 |
| `migrations/models/5_..._access_models.py` | aerich 생성 + raw SQL: `role_permissions` 복합 PK, `user_roles` `NULLS NOT DISTINCT` 유일 인덱스, 범위 check, enum CHECK, 기본값. downgrade 순서 수정 |
| `contexts/access/application/roles.py` | `RoleCatalogSeeder`, `RoleAssignmentService`(멱등 부여), `RoleQueries` |
| `contexts/identity/application/user_admin.py` | `UserAdministration.ensure_approved_staff`: 운영진 도메인 이메일 확인, 없으면 생성, 승인. 탈퇴·정지 계정 거부 |
| `contexts/access/application/bootstrap.py` | `SuperAdminBootstrap`: 시드 → 회원 승인 → SUPER_ADMIN 부여 → 감사 로그 (한 트랜잭션) |
| `app/cli.py` | `python -m app.cli create-super-admin <email> [--name]`, `seed-roles` |
| `/me` | 만료되지 않은 역할 목록 추가 (`app.state.role_queries`, B10) |
| `tests/conftest.py` | 테스트 `Settings`가 로컬 `.env`와 compose 환경변수에 영향받지 않게 고정 |

## 주요 결정
- **사용자 결정 (A14):** 최고 관리자는 이메일만 넣으면 등록되는 CLI로 만든다. A12에서 계획한 "로그인·신청 후 CLI로 승인"을 대체한다. 부서·직위 시드는 만들지 않는다.
- 회원이 없으면 승인된 회원을 미리 만든다. 그 이메일로 처음 Google 로그인하면 이메일로 연결된다(P2-1의 연결 규칙). 그래서 CLI를 로그인보다 먼저 실행해도 된다.
- 운영진 도메인(`nextrunners.co.kr`) 이메일만 받는다. 운영진은 Google 도메인 로그인으로만 들어오기 때문이다.
- 최고 관리자는 직원(`employees`) 등록 없이도 된다. 부트스트랩 관리자가 조직 데이터를 넣기 전에 존재해야 하기 때문이다. 신청해 둔 가입 신청이 있으면 PENDING으로 남고, P3-2 승인 API로 처리한다.
- 역할·권한 정의는 코드가 원천이다. 시드는 정의에 맞춰 매핑을 추가·정리하지만, 정의에서 빠진 역할·권한 행은 부여 이력 보존을 위해 지우지 않는다.
- CLI 위치는 계획서의 `scripts/seed_roles.py` 대신 `app/cli.py`로 했다. 패키지 안에 두어야 컨테이너에서 `python -m`으로 바로 실행되고 테스트에서 import할 수 있다.

## 발견한 문제와 해결
- `.env`를 채운 뒤 기존 테스트 2개가 실패했다(Google 미설정 503, 500 오류 응답 형식). 원인은 두 경로로 들어온 값이다. `Settings`가 `.env`를 읽었고, compose `env_file`도 같은 값을 컨테이너 환경변수로 넘겼다. 테스트 설정에서 `.env`를 끄고 결과에 영향을 주는 값(`debug`, `google_*`, 쿠키)을 고정했다. 이 수정은 별도 `test:` 커밋으로 뒀다.
- 실행 중이던 api 컨테이너는 `.env`가 생기기 전에 만들어져 Google 설정이 비어 있었다. `docker compose up -d --force-recreate api`로 다시 만들었다.
- CLI 출력에 Tortoise의 "has no models" 경고(아직 모델이 없는 educator·mentoring 모듈)가 섞여 CLI에서만 숨겼다.
- Google 인가 URL로 접속하면 `redirect_uri_mismatch`(Error 400)가 난다. Google Cloud Console에 `GOOGLE_REDIRECT_URI` 값이 승인된 리디렉션 URI로 등록되어 있지 않은 것으로 보인다. 사용자에게 확인을 요청했다(코드 문제 아님).

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports(10개 계약 유지), pytest **181개 통과**(통합 포함)
- 개발 DB:
  - `aerich upgrade` 성공
  - `aerich migrate` → "No changes detected"
  - `aerich downgrade -v 4` → `upgrade` 성공
- 개발 DB에서 CLI 실행 (임시 이메일, 확인 후 삭제):
  - 신규 이메일 → 회원 생성 + SUPER_ADMIN 부여
  - 재실행 → 변경 없음
  - gmail 이메일 → `not_staff_email`로 실패(종료 코드 1)
  - 역할 5개와 역할별 권한 수 확인: SUPER_ADMIN 12, 매니저 10, 조교 6, 멘토·수강생 0
- 실행 중인 api: CLI로 등록한 회원의 토큰으로 `/me` → APPROVED, `roles=[SUPER_ADMIN/GLOBAL]`

## 남은 작업
- P3-2: `require_permission`과 범위 판정, 운영진 가입 승인·반려 API, 담당자 배정과 `user_roles` 동기화
- P3-3: 담당자·역할 관리 API
- Google Cloud Console에 리디렉션 URI 등록 후 실제 로그인 확인
