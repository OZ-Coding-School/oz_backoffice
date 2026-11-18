# 63. 계정 종류를 수강생·멘토·운영진으로 나눔

- 상태: PR 진행 중
- 관련 PR: #82
- 관련 결정: `docs/decisions.md` A65 (A61 변경)
- 이전 기록: [62. 수강생 멘토링 신청 준비 API (BE-1)](62_student_mentoring_prep.md)

## 배경
FE-2(회원 공통 틀)는 수강생 틀과 멘토 틀을 나눠 보여 준다. 그런데 `/me`로는 둘을 구분할 수 없었다.
- 계정 종류는 MEMBER/STAFF뿐이었다.
- 멘토는 MENTOR 역할을 쓰지 않는다(A35). 그래서 "STUDENT 역할이 없으면 멘토"로 추측해야 했고, 수강이 끝난 수강생을 멘토로 잘못 볼 수 있었다.

사용자가 한 계정이 두 역할을 함께 갖지 않도록 하고, `account_type` 자체를 STUDENT·MENTOR·STAFF로 나누자고 정했다.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `identity/domain/enums.py` | `AccountType`: STUDENT·MENTOR·STAFF. `member_account_type(signup_type)` |
| `identity/domain/entities.py` | `User.change_member_type`: 승인 전 수강생 ↔ 멘토만. 승인된 계정·운영진은 `account_type_locked` |
| `identity/application/signup.py` | 이메일 가입은 가입 유형대로 계정 종류를 정한다 |
| `identity/application/signup_review.py` | 재신청할 때 계정 종류도 새 유형으로 바꾼다. 수강생·멘토 승인은 계정 종류와 신청 유형이 같을 때만 한다(`signup_type_mismatch`) |
| `identity/presentation/schemas.py` | `/me`의 `account_type` 설명 |
| `migrations/models/25_…_account_type_member_split.py` | CHECK `check_users_account_type`를 STUDENT·MENTOR·STAFF로 바꾼다. 값은 옮기지 않는다 |
| `docs/database_schema_v2.dbml` | `Enum AccountType`, 컬럼 설명, check |
| 프론트엔드 `guards.ts`, `navigation.ts`, `_member.tsx`, `_staff.tsx` | `MEMBER` 검사를 `isMember`(STAFF가 아님)로 바꿨다. `requireAccount`는 들어갈 수 있는 계정 종류 목록을 받는다 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 다시 만들었다(F19) |

## 주요 결정 (사용자 결정, A65)
- 계정 종류는 STUDENT·MENTOR·STAFF 중 하나다. 한 계정이 수강생과 멘토 역할을 함께 갖지 않는다.
- 반려된 회원이 승인 전에 다른 유형으로 재신청하면 계정 종류도 바뀐다. 승인된 뒤에는 바뀌지 않는다.
- 마이그레이션은 CHECK만 바꾸고 값을 옮기지 않는다. 개발 DB의 회원은 사용자가 직접 지웠다.

## 검증
- 개발 DB: `aerich upgrade` → `aerich migrate`("No changes detected") → `aerich downgrade -v 25` → `aerich upgrade`
- DBML: `dbmlv2` 파서 통과
- 테스트
  - 단위: 계정 종류 변경 규칙(승인 전만, 운영진 불가), 멘토 가입 → MENTOR
  - API: 재신청에서 유형을 바꾸면 계정 종류와 `/me`가 바뀐다. 계정 종류와 신청 유형이 다르면 승인 422
  - 통합: 저장·조회, raw insert
- 로컬 검사 (compose `api`): ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 869 passed.
- 프론트엔드: `lint`, `format:check`, `typecheck`, `test`(82), `build`, `e2e`(9) 통과

## 남은 작업
- FE-2: `account_type`으로 수강생 틀과 멘토 틀을 고른다
