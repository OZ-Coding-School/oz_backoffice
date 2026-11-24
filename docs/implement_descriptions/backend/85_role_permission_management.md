# 85. 역할별 권한 DB 판정·역할 관리 API (BE-3d)

- 상태: PR 진행 중
- 관련 PR: (작성 중)
- 관련 결정: `docs/decisions.md` A84, F63 (A16·A17 변경)
- 이전 기록: [84. 직원 목록 검색·팀 필터·담당 (BE-3c)](84_employee_list_assignments.md)

## 배경
FE-15d 역할·권한 화면에서 역할별 권한 표를 고치고 운영진 역할을 새로 만들기로 했다(A84). 지금은 역할 → 권한 묶음이 코드(`catalog.py`)에 고정돼 있고 DB `role_permissions`는 판정에 쓰지 않는 사본이라(A16), 화면에서 고쳐도 권한이 바뀌지 않는다.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `access/domain/catalog.py` | 코드는 권한 목록·기본 역할·**초기값**. `GLOBAL_ONLY_PERMISSIONS`(org.manage·role.assign·staff.assign), `BUILTIN_ROLE_CODES`, `HIDDEN_ROLE_CODES`(멘토·수강생) |
| `access/domain/enums.py`, `domain/roles.py` | `RoleScopeKind`(GLOBAL·SCOPED), 역할 엔티티 `Role`: 코드·이름·설명 규칙, 권한 교체(최고 관리자·멘토·수강생 잠금, 없는 권한, 범위 역할의 전체 전용 권한 422), 최고 관리자 유효 권한 = 전체 |
| `access/domain/entities.py` | `RoleGrant.permissions`. 새 역할의 범위는 서비스가 검사하도록 `UserRole`은 기본 역할만 범위 검사 |
| `access/infrastructure/models.py`, `migrations/models/30_*` | `roles.scope_kind`(null = 기본 역할, CHECK GLOBAL·SCOPED) |
| `access/infrastructure/repositories.py` | 시드는 **없는 권한·역할만** 만들고 새 역할에만 초기 묶음(최고 관리자는 빠진 권한 채움). 사용자 역할을 읽을 때 역할 권한을 함께 읽음. `TortoiseRoleRepository`(목록·잠금·이름 중복·저장·삭제·보유자 수) |
| `access/application/permissions.py` | 판정을 `RoleGrant.permissions`(DB)로 |
| `access/application/role_catalog.py` | 역할 목록·추가·이름 수정·권한 교체·삭제, 감사 로그 `access.role_definition.*` |
| `access/presentation/role_router.py` | `GET/POST /admin/roles`, `PATCH/DELETE /admin/roles/{code}`, `PUT /admin/roles/{code}/permissions` (role.assign) |
| `docs/database_schema_v2.dbml` | `roles.scope_kind`·CHECK, `role_permissions`가 판정 출처 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 생성 타입 갱신 |

- 응답의 권한은 권한 정의 순서, 역할은 기본 역할(정의 순서) → 새 역할(만든 순서). 보유자 수는 만료된 부여까지 센 회원 수다(부여 행이 있으면 지울 수 없으므로).
- 판정은 요청당 사용자 역할 조회 1번 + 역할 권한 prefetch 1번이다.
- 오류 코드: `invalid_role_code`·`invalid_role_name`·`invalid_role_description`·`permission_not_found`·`global_only_permission`·`role_permissions_locked`·`builtin_role`(422), `role_code_taken`·`role_name_taken`·`role_in_use`(409), `role_not_found`(404, 멘토·수강생 포함).

## 주요 결정 (사용자 결정, A84·F63)
- RBAC 유지(사람 → 역할 → 권한), 권한 표는 화면에서 편집, 코드 권한표는 초기값만, 최고 관리자만 고정(role.assign은 다른 역할에도 켤 수 있음), 역할 추가·삭제(보유자 있으면 막기), 범위는 만든 뒤 고정, 범위 역할에 전체 전용 권한 금지, 코드 직접 입력·이름 중복 불가·설명 200자, 표 전체 [저장], `role.assign`만, PR은 BE 2개 + FE 2개.

## 발견한 문제와 해결
- 시드(`seed-roles`, `create-super-admin`)가 매번 매핑을 정의대로 되돌려 화면에서 고친 권한을 덮었다. 없는 것만 추가하도록 바꾸고 통합 테스트로 확인했다.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 930 passed (통합 포함). 단위: 역할 규칙(코드·이름·설명 경계, 잠금, 전체 전용 권한), 저장된 매핑으로 판정. 통합: 시드가 고친 매핑·이름을 덮지 않고 최고 관리자 권한을 채움. API: 새 역할 권한을 켜고 끄면 보유자의 접근이 바로 바뀜, 팀리드에서 staff.assign을 빼면 403, 오류 코드, role.assign 아닌 운영진 403·비로그인 401
- 마이그레이션: `aerich upgrade` → `aerich migrate`(No changes detected) → `aerich downgrade -v 30` → `aerich upgrade`
- DBML 파서(@dbml/core 11) 검증 통과
- 프론트엔드: `typecheck` 통과

## 남은 작업
- BE-3e 역할 보유자 목록·직접 부여 확장(새 역할·범위)
- FE-15d 역할별 권한 탭, FE-15e 역할 보유자 탭
- 운영 배포 시 `seed-roles`는 그대로 실행해도 고친 매핑을 덮지 않는다
