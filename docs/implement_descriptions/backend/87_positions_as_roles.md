# 87. 직위 = 역할, 최고 관리자 필드, 데이터 범위 (BE-3g)

- 상태: PR 진행 중
- 관련 PR: (작성 중)
- 관련 결정: `docs/decisions.md` A87·A88 (A84·A85·A16·A17·A36 변경)
- 이전 기록: [86. 권한 엔터티 × 조회/관리 세분화 (BE-3f)](86_entity_permissions.md)

## 배경
권한 화면 시안을 보면서 기본 역할과 새 역할의 경계, 전체/과정·기수 범위의 경계를 모두 없애기로 했다(A87). 직위가 곧 역할이 되어 직위에 권한 묶음과 데이터 범위가 붙고, 최고 관리자는 회원 필드가 된다. 별도의 역할 테이블과 역할 부여는 없앤다.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `access/domain/catalog.py` | 역할 정의·대응표 제거. 권한마다 `cohort_bound`(기수에 속한 엔터티), `validate_permissions`(정의된 코드만, 관리·특별 동작은 조회와 함께), 개발 직위 묶음 `DEV_POSITION_PERMISSIONS` |
| `access/application/permissions.py`, `grant_source.py` | 판정: 최고 관리자 → 모든 권한·데이터, 직원 → 직위 권한. 기수 엔터티는 직위 데이터 범위가 '전체'면 모두, '담당만'이면 담당 과정(소속 기수 포함)·기수만. 그 밖의 엔터티는 권한만 |
| `access` 역할 코드 삭제 | `roles.py`·`role_admin.py`·`role_catalog.py`·역할 엔티티·저장소·모델·`/admin/roles`·`/admin/users/{id}/roles` |
| `access/presentation/permission_router.py`, `super_admin_router.py` | `GET /admin/permissions`(권한 정의, access.role.read), `PUT /admin/users/{id}/super-admin`(최고 관리자만, 422 `staff_only`, 409 `last_super_admin`) |
| `access/presentation/me_router.py` | `GET /me/staff-access`에 `is_super_admin`·`position`(이름·데이터 범위) |
| `identity` | `users.is_super_admin`, `set_super_admin`(운영진·승인·활성만), 마지막 1명 잠금 조회, `/me`의 `roles` → `is_super_admin`, 가입 승인·자동 매칭이 수강생 역할을 붙이지 않음 |
| `organization` | 직위 `data_scope`(ASSIGNED·ALL), `position_permissions`, 직위 응답에 권한·직원 수, `PUT /admin/positions/{id}/permissions`(access.role.manage), `EmployeeQueries.access_of`. 담당자 배정·운영진 승인이 역할을 붙이지 않음(`staff_roles.py` 삭제) |
| `migrations/models/31_*` | `users.is_super_admin`, `employee_positions.data_scope`(CHECK), `position_permissions` 추가, 역할 테이블 4개 삭제(되돌리면 다시 만듦) |
| `cli.py` | `seed-roles` 삭제, `create-super-admin`은 회원 필드, `seed-dev-org`가 직위 데이터 범위와 권한(비어 있을 때만) |
| `docs/database_schema_v2.dbml` | 위 스키마 |
| `apps/frontend` | 생성 타입, 사용자 메뉴 역할 줄(최고 관리자·직위·데이터 범위), 테스트 데이터 |
| `tests/factories/access.py` | 직위 권한·담당으로 예전 역할 셋업을 옮기는 `give_role`·`give_permissions` |

- 판정은 요청당 회원·직원·직위·권한·담당을 한 번씩 읽는다.
- 담당자 행의 역할 칸(운영 매니저·조교)과 A63 변경은 다음 PR(BE-3h)에서 한다(A88).

## 주요 결정 (사용자 결정, A87·A88)
- 직위 = 역할(직원당 하나), 최고 관리자는 회원 필드(CLI + 화면), 수강생·멘토 역할 없음, 권한 범위 구분 없음·데이터 범위는 직위 속성 + 담당 배정, 역할 테이블은 데이터 없이 삭제, 백엔드 PR은 CI 통과 후 바로 병합.

## 발견한 문제와 해결
- 개발 DB의 최고 관리자 역할이 테이블과 함께 사라진다. 배포 전이라 데이터를 옮기지 않기로 했으므로 `create-super-admin`을 다시 실행해야 한다(배포 참고사항에 적음).

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 888 passed (통합 포함)
  - 단위: 판정(권한 없음, 기수 무관 엔터티, 전체 데이터, 담당 과정·기수, 요청당 한 번), 권한 출처, 권한 정의·검사
  - API: 직위 권한·데이터 범위를 바꾸면 접근이 바로 바뀜, 권한 규칙 422, 권한 정의, 최고 관리자 켜기·끄기·마지막 1명·운영진만·최고 관리자만
- 마이그레이션: `aerich upgrade` → `migrate`(No changes) → `downgrade -v 31` → `upgrade`, DBML 파서 검증
- 개발 DB: `seed-dev-org`로 직위 권한·데이터 범위 확인(팀리드 25·전체, 운영 매니저·러닝 코치 22, 조교 12)
- 프론트엔드: `lint`, `format:check`, `typecheck`, `vitest` 304 passed, `build`, Playwright E2E 39 passed

## 남은 작업
- BE-3h 담당 역할 칸 제거·A63 변경·직원 수정에서 담당 지정(A88)
- FE-15d 조직 설정 모듈 + 권한 화면
