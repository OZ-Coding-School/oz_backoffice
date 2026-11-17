# 59. 계정 종류(account_type)와 운영진 로그인 실패 경로

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A61, F20 (프론트엔드 계획 BE-0)
- 이전 기록: [58. refresh 재사용 유예 시간](58_refresh_reuse_grace.md)

## 배경
FE-1(인증 화면)을 설계하다가 백엔드에 두 가지가 모자란 것을 확인했다.
- **승인 전 사용자를 구분할 수 없다.** 프론트는 승인 전(역할 없음) 사용자를 회원이면 가입 상태 모달로, 운영진이면 최초 정보 입력 화면으로 보내야 한다. 그런데 `GET /me`에는 둘을 구분할 값이 없었다.
- **Google 로그인 실패 경로가 맞지 않는다.** 실패하면 수강생·멘토 로그인(`/login`)으로 돌아갔다. Figma에서는 운영진 로그인 화면(`/staff/login`)에 오류를 보여 준다.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `identity/domain/enums.py`, `entities.py` | `AccountType`(MEMBER/STAFF)을 추가했다. `User.account_type`은 필수 값이다 |
| `identity/infrastructure/models.py`, `repositories.py` | `users.account_type` 컬럼과 매핑 |
| `migrations/models/23_…_user_account_type.py` | 컬럼 추가. 개발 DB의 기존 행은 비밀번호가 있으면 MEMBER, 없으면 STAFF로 채운 뒤 NOT NULL로 만들고 CHECK `check_users_account_type`을 건다 |
| `identity/application/signup.py` | 이메일 가입 → MEMBER |
| `identity/application/auth_service.py` | Google 로그인으로 새로 만든 계정 → STAFF |
| `identity/application/user_admin.py` | CLI 최고 관리자 → STAFF |
| `identity/presentation/schemas.py`, `router.py` | `MeResponse.account_type`. Google 콜백 실패 리디렉션을 `/staff/login?error=<code>`로 바꿨다 |
| `docs/database_schema_v2.dbml` | `users.account_type`, `Enum AccountType`, check 제약 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 새 응답 필드에 맞춰 다시 만들었다(F19 규칙) |

## 주요 결정 (사용자 결정, A61·F20)
- 구분은 `/me`에 `account_type`을 추가하는 방식으로 하고, `users`에 컬럼을 둔다.
- 값은 가입 경로로 정하고 바꾸지 않는다(수정 API 없음).
- 서비스 전이라 기존 사용자 데이터는 고려하지 않는다.
- Google 로그인 실패는 `/staff/login?error=`로 보낸다. 운영진 정보 입력 화면 경로는 `/staff/registration`이다.

## 검증
- **DBML:** `@dbml/core` 11의 `dbmlv2` 파서로 통과했다. 이전 `dbml` 파서는 이번 변경 전의 파일에서도 실패한다.
- **개발 DB:** `aerich upgrade` → `aerich migrate`("No changes detected") → `aerich downgrade -v 23` → `aerich upgrade`
- **테스트**
  - API: `/me`의 `account_type`(Google 로그인 계정 STAFF), Google 콜백 실패 경로 `/staff/login?error=`
  - 통합: 저장·조회 왕복(MEMBER), CHECK 제약 위반(`ADMIN`), raw insert, CLI 최고 관리자 STAFF
  - 단위: 이메일 가입 MEMBER
- **로컬 검사 (compose `api`):** ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 840 passed.
- **프론트엔드:** 다시 만든 타입으로 `typecheck`·`test` 통과

## 남은 작업
- FE-1a~1c: `account_type`과 `approval_status`로 로그인 후 경로를 정하고, 운영진 로그인 화면에서 `?error=` 문구를 보여 준다.
- Figma 캡션(운영진 로그인 실패 경로, `/staff/register` 잠정 표기)은 FE-1c에서 고친다.
