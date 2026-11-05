# 08. P2-1 인증 기반과 운영진 Google 로그인

- 상태: PR 진행 중
- 관련 PR: #11
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P2 (P2-1)
- 이전 기록: [07. 수강생 명단을 students에 합침](07_merge_student_rosters_into_students.md)

## 배경
P2는 첫 API다. 운영진이 Google 계정으로 로그인하고 토큰을 발급·갱신·폐기하는 기반을 만든다. 계획서에는 "employees에 없으면 로그인 거부"라고 적혀 있었다. 하지만 직원 등록 API(P4)가 없는 상태에서 최초 관리자가 로그인할 수 없어서, 사용자와 운영진 가입 흐름을 다시 정했다(decisions A11·A12).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `integrations/google/oauth.py` | 인가 URL(state·PKCE S256·`hd` 힌트), code 교환, ID 토큰 클레임 검증(`aud`·`iss`·`exp`·`email_verified`·`hd`·이메일 도메인) |
| `contexts/identity/domain/sessions.py` | refresh 토큰·OAuth state 저장소 Protocol |
| `contexts/identity/infrastructure/token_store.py` | Redis 구현. 활성 jti, 회전·폐기된 jti(재사용 탐지), 사용자별 jti 집합(전체 폐기), OAuth state(10분·1회용, `GETDEL`) |
| `contexts/identity/application/tokens.py` | `TokenService`: 발급, refresh 1회 소비(회전), 재사용 시 사용자 refresh 전체 폐기, 로그아웃 |
| `contexts/identity/application/auth_service.py` | `StaffGoogleLoginService`(첫 로그인 시 PENDING 회원 생성 또는 같은 이메일 회원에 연결), `SessionService`(갱신·로그아웃), `UserQueries`(현재 사용자 확인, 공개 서비스) |
| `contexts/identity/domain/entities.py` | `User.can_login`: 탈퇴 또는 승인 후 비활성(정지)이면 로그인 불가. 승인 전에는 비활성이어도 로그인 가능 |
| `contexts/identity/presentation/` | `/auth/google/authorize`·`/callback`·`/refresh`·`/logout`, `/me`. refresh는 `oz_refresh` 쿠키(HttpOnly·Secure·SameSite=Lax·Path=`/api/v1/auth`) |
| `contexts/access/presentation/dependencies.py` | 공개 인증 의존성 `get_current_user`(`CurrentUser`), `require_approved_user`(`ApprovedUser`, 승인 전 403 `approval_required`) |
| `core/dependencies.py`, `main.py` | 설정·시계·JWT·HTTP 클라이언트 의존성. `app.state.clock`, `app.state.user_queries`, lifespan의 `httpx.AsyncClient` |
| `shared/errors.py`, `core/errors.py` | `ServiceUnavailableError` → 503 (Google 클라이언트 미설정) |
| `tests/` | Google 어댑터(respx), 토큰 회전·재사용·만료(fakeredis), 로그인 유스케이스(인메모리 리포지토리·가짜 Google·`FakeUnitOfWork`), API(쿠키 속성, state 위조, PENDING 게이트, 회전·재사용, 로그아웃, 미설정 503) |

## 주요 결정
- **사용자 결정 (A11):** 도메인 계정이면 로그인시키고 처음이면 PENDING 회원을 만든다. 최초 로그인 후 부서·직위·담당 과정/기수를 입력하고, 어드민이 항목을 조정해 승인하면 이용할 수 있다. 담당 역할과 과정·기수는 신청자가 직접 고른다.
- **사용자 결정 (A12):** P2에서 로그인과 신청 입력을, P3에서 권한과 함께 승인 API와 최초 어드민 CLI를 만든다. 신청 입력은 P2-2 PR에서 이어서 만든다.
- ID 토큰은 서명 검증 없이 클레임만 검증한다(A13). 토큰 엔드포인트에서 HTTPS로 직접 받기 때문이고, `cryptography` 의존성을 추가하지 않기 위해서다.
- 인증 의존성은 공개 영역인 `access.presentation`에 둔다. 회원 조회 서비스는 `app.main`이 `app.state`에 연결한다(B10). 이렇게 해서 import-linter 계약을 바꾸지 않았다.
- Redis 키는 하네스 규칙(`oz:<컨텍스트>:...`)을 따라 `oz:identity:refresh:<jti>`로 정했다. 계획서의 `oz:refresh:<jti>`도 같이 고쳤다.
- 로그인 자체는 감사 로그 필수 대상이 아니어서 기록하지 않는다.

## 발견한 문제와 해결
- 처음에는 refresh 저장소 Protocol을 `application`에 두었다. 그러자 `infrastructure`가 `application`을 import하게 되어 계층 계약이 깨졌다. Protocol과 `RefreshLookup`을 `domain/sessions.py`로 옮겼다. push 전이라 해당 커밋을 다시 만들었다.
- `get_google_authenticator`가 HTTP 클라이언트를 먼저 꺼내다가 lifespan 밖(테스트)에서 500이 났다. 설정 확인을 먼저 하도록 순서를 바꿨다.
- 같은 refresh로 동시에 갱신하면 하나만 성공하고 나머지는 재사용으로 판정되어 전체 로그아웃된다(`GETDEL` 원자성). 프론트엔드는 갱신 요청을 하나로 모아야 한다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports(10개 계약 유지), pytest **124개 통과**(통합 포함)
- 실행 중인 api 컨테이너 확인:
  - `/auth/google/authorize`(클라이언트 미설정) → 503 `google_login_not_configured`
  - `/me`(토큰 없음) → 401
  - `/auth/refresh`(쿠키 없음) → 401
  - OpenAPI에 경로 5개 노출
- 실제 Google 계정 로그인은 OAuth 클라이언트 ID·시크릿을 받은 뒤 확인한다

## 남은 작업
- P2-2: 운영진 최초 정보 입력(신청 테이블·API)
- P3: 승인·반려 API, 최초 어드민 CLI, `/me`에 역할 추가
- Google OAuth 클라이언트(ID·시크릿, 승인된 리디렉션 URI) 발급 후 실제 로그인 확인
