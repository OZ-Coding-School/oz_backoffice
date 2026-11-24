# 86. 역할 보유자 목록·직접 부여 확장 (BE-3e)

- 상태: PR 진행 중
- 관련 PR: #133
- 관련 결정: `docs/decisions.md` A85, F63 (A17·A84)
- 이전 기록: [85. 역할별 권한 DB 판정·역할 관리 API (BE-3d)](85_role_permission_management.md)

## 배경
FE-15e 역할 보유자 탭은 누가 어떤 운영진 역할을 가졌는지 사람 단위로 보여 주고, 최고 관리자·팀리드와 BE-3d에서 만든 **새 역할**을 직원에게 주고 회수한다. 지금은 회원 한 명의 역할 조회만 있고 보유자 목록이 없으며, 직접 부여는 최고 관리자·팀리드를 전체 범위로만 줄 수 있다(A17).

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `access/domain/roles.py` | `is_directly_managed`: 최고 관리자·팀리드·새 역할 |
| `access/domain/repositories.py`, `infrastructure/repositories.py` | `list_holder_ids`(멘토·수강생 제외, 역할 필터, 이름·이메일 검색, 이름순, 만료 포함), `list_by_users` |
| `access/application/role_holders.py` | 보유자 목록: 회원(identity)·소속(organization)·과정·기수 이름(academy)을 묶음으로 읽어 사람 단위로 |
| `access/application/role_admin.py` | 직접 부여 확장: 새 역할, `scope_type`·`scope_id`(역할의 허용 범위와 맞아야 함, 과정·기수 존재 검사), 운영진 계정만(`staff_only`), 감사 로그에 범위 |
| `access/presentation/holder_router.py` | `GET /admin/role-holders?role=&q=&limit=&offset=` (role.assign) |
| `access/presentation/admin_router.py` | 부여 요청에 `scope_type`·`scope_id`, `managed_by`는 `is_directly_managed` 기준 |
| `organization/application/employee_queries.py` | `affiliations(user_ids)`: 부서·팀·직위 이름 (`list_by_users`) |
| `main.py` | `employee_queries`에 부서·팀·직위 저장소 연결 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 생성 타입 갱신 |

- 보유자 목록은 요청당 쿼리 수가 고정이다(보유자 ID, 부여, 역할 이름, 회원, 소속, 과정·기수 이름). 운영진 보유자는 많지 않아 회원 단위로 모은 뒤 자른다.
- 오류 코드: `invalid_role_scope`·`staff_only`·`role_managed_by_assignment`·`role_not_found`(422), `bootcamp_not_found`·`cohort_not_found`(404), `role_already_granted`(409).

## 주요 결정 (사용자 결정, A85)
- 목록 `GET /admin/role-holders` 사람 단위·이름순·역할 필터는 사람을 고르고 다른 역할도 표시, 만료 부여는 '만료' 표시로 포함, 기존 부여 API 확장, 직접 부여 대상은 운영진 계정만.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 935 passed (통합 포함)
  - 통합: 새 범위 역할을 기수·과정으로 각각 부여·회수, 범위 오류·없는 과정·기수, 수강생 계정 `staff_only`
  - API: 사람 단위·이름순·소속·과정명·기수 번호·관리 방식, 수강생 역할 제외, 역할 필터·검색·페이지, 만료 표시, role.assign 아닌 운영진 403·비로그인 401
- 프론트엔드: `typecheck` 통과

## 남은 작업
- FE-15d 역할별 권한 탭, FE-15e 역할 보유자 탭
