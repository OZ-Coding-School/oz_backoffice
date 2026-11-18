# 60. 조직 구조: 부서·팀과 직위 담당 방식

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A62 (A11 변경)
- 이전 기록: [59. 계정 종류(account_type)와 운영진 로그인 실패 경로](59_account_type.md)

## 배경
FE-1c(운영진 최초 정보 입력)를 테스트하다가 담당 선택 방식을 바꿔야 한다는 결정이 나왔다. 직위에 따라 고르는 대상이 다르다.
- 팀리드·운영 매니저·러닝 코치는 담당 과정을 여러 개 고른다.
- 조교는 담당 기수를 하나 고른다.

고를 수 있는 과정은 소속 팀이 담당하는 과정이어야 한다. 그래서 조직 구조도 함께 바꿨다.
- 기존: 상위 부서 트리 `departments.parent_id`
- 변경: 부서와 팀으로 나누고, 과정마다 담당 팀을 하나 둔다.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `organization/domain/entities.py`, `enums.py` | `Department`에서 상위 부서를 없앴다. `Team`(한 부서 소속), `BootcampTeam`(과정당 한 팀), `AssignmentScope`(COURSE/COHORT)를 추가했다. `EmployeePosition.assignment_scope`, `Employee.team_id`도 추가했다 |
| `organization/domain/registration.py` | 신청에 `team_id`를 추가하고, 직위 담당 방식 규칙 `check_assignment_scope`를 추가했다 |
| `organization/domain/repositories.py`, `infrastructure/*` | `teams`·`team_bootcamps` 모델과 리포지토리를 추가했다. 부서 이름 조회를 바꾸고, 팀 참조 확인·이동을 추가했다 |
| `migrations/models/24_…_org_teams.py` | 아래 "마이그레이션" 참고 |
| `organization/application/org_service.py` | 팀 CRUD를 추가했다. 삭제할 때 참조를 옮긴다. 과정 담당 팀 지정, 직위 담당 방식, 직원 팀 이동도 추가했다. 부서의 상위·순환 검사는 없앴다 |
| `organization/application/registration_service.py` | 신청 선택지에 팀과 과정-팀 연결을 넣었다. 검증은 신청할 때만 엄격하게 한다(`strict`): 팀이 부서 소속인지, 직위 담당 방식에 맞는지 본다 |
| `organization/application/review_service.py` | 승인 조정에 팀을 추가했다(존재만 검사). 승인하면 직원에 팀을 반영한다 |
| `organization/presentation/*` | `/admin/teams` CRUD, `PUT /admin/bootcamps/{id}/team`, 직위 `assignment_scope`, 직원·신청 `team_id`를 추가했다. 신청 선택지에 `teams`, `positions[].assignment_scope`, `bootcamps[].team_id`를 넣었다 |
| `academy/application/catalog.py` | `get_bootcamp` 추가 (과정 담당 팀 지정 시 존재 확인) |
| `app/cli.py` | `seed-dev-org`: 개발용 부서·팀·직위와 과정 담당 팀 (멱등, local·test 전용) |
| `docs/database_schema_v2.dbml` | `teams`, `team_bootcamps`, `Enum AssignmentScope`, 컬럼 추가, `departments.parent_id` 제거 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 다시 만들었다(F19) |
| `apps/backend/CLAUDE.md` | 시드 명령. 마이그레이션은 데이터를 넣지 않는다는 규칙. `aerich downgrade -d` 주의 |

### 마이그레이션 (24)
- **스키마만 바꾼다.**
  - 테이블 `teams`(부서 FK, `(department_id, name)` 유일)와 `team_bootcamps`(`bootcamp_id` 유일)를 만든다.
  - `employee_positions.assignment_scope`를 추가하고 CHECK를 건다(COURSE/COHORT/null).
  - `employees.team_id`, `employee_registrations.team_id`를 추가한다(nullable, RESTRICT).
  - `departments.parent_id`를 없애고(FK·CHECK·`(parent_id, name)` 인덱스가 함께 빠진다) 부서 이름에 유일 인덱스를 건다.
- **데이터는 넣거나 옮기지 않는다**(사용자 결정). 기존 하위 부서는 부서로 남는다. 운영 데이터는 아직 없다.
- downgrade는 `parent_id`와 그 제약·인덱스를 되살리고 새 테이블·컬럼을 지운다.

### API

| API | 내용 |
| --- | --- |
| `GET/POST /admin/teams`, `PATCH/DELETE /admin/teams/{id}` | 팀 목록(담당 과정 `bootcamp_ids` 포함)·생성·수정(부서 이동 가능)·삭제 |
| `DELETE /admin/teams/{id}?move_to_team_id=` | 직원·가입 신청(이력 포함)·담당 과정이 있으면 이동할 팀으로 옮긴 뒤 지운다. 이동할 팀 없이 참조가 있으면 409 `team_in_use`. 같은 팀이면 422 `invalid_move_to_team` |
| `PUT /admin/bootcamps/{id}/team` | 과정 담당 팀을 지정한다. `null`이면 해제한다. 없는 과정이면 404 `bootcamp_not_found` |
| `POST/PATCH /admin/positions` | `assignment_scope`. PATCH에서 `null`을 보내면 담당 없음 |
| `PATCH /admin/employees/{id}` | `team_id`. `null`을 보내면 부서 직속 |
| `GET /me/staff-registration/options` | `departments`(상위 없음), `teams`, `positions[].assignment_scope`, `bootcamps[].team_id` |
| `PUT /me/staff-registration` | `team_id`를 받는다. 규칙을 어기면 422: `team_not_in_department`, `invalid_staff_assignment` |
| `POST /admin/staff-registrations/{id}/approve` | `team_id`. 보내지 않으면 신청값을 쓰고, `null`이면 팀을 뺀다. 검사는 존재만 한다 |

### 신청 규칙 (`check_assignment_scope`, 신청할 때만)
- 담당이 없으면 항상 통과한다(0개 허용, F25).
- 직위 담당 방식이 없으면 담당을 고를 수 없다.
- COURSE: 운영 매니저 역할 + 소속 팀 과정. 여러 개를 고를 수 있다(최대 20).
- COHORT: 조교 역할 + 소속 팀 과정의 기수. 하나만 고를 수 있다.
- 팀이 없으면(부서 직속) 고를 수 있는 과정이 없으므로 담당 없이만 신청할 수 있다.

## 주요 결정 (사용자 결정, A62)
- 부서와 팀을 나눈다. 직원과 신청은 부서 필수, 팀 선택이다.
- 과정은 담당 팀 하나에 속하고, 관리자가 바꾼다.
- 직위의 담당 방식은 COURSE / COHORT / null이다.
- 규칙은 신청할 때만 강제한다. 승인 조정과 직원 수정은 자유다(존재만 검사).
- 팀 설명은 선택이다. 팀은 다른 부서로 옮길 수 있다.
- 팀을 지울 때는 참조를 다른 팀으로 옮겨야 한다. 삭제 API가 이동할 팀을 받는다.
- 마이그레이션은 데이터를 넣지 않는다. 개발 데이터는 CLI 시드로 넣는다.

## 발견한 문제와 해결
- 마이그레이션 검증 중 `aerich downgrade -v 24 -d`를 실행했다. `-d`는 마이그레이션 파일까지 지운다. 커밋 전이라 `aerich migrate`로 같은 파일을 다시 만들고 raw SQL을 다시 넣었다. 같은 실수를 막도록 백엔드 CLAUDE.md에 주의를 적었다.
- 첫 구현은 마이그레이션에서 하위 부서를 팀으로 바꿨다. 사용자 결정에 따라 데이터 변환을 모두 뺐다.

## 검증
- **DBML:** `@dbml/core` 11 `dbmlv2` 파서로 통과했다.
- **개발 DB:** `aerich upgrade` → `aerich migrate`("No changes detected") → `aerich downgrade -v 24` → `aerich upgrade`
  - `seed-dev-org`를 두 번 실행했다. 두 번째는 "바꿀 것이 없습니다"였다.
- **테스트**
  - 단위: 팀·직위·직원 엔티티, `check_assignment_scope`(방식별 허용·거부, 기수 하나), 신청 서비스(팀-부서 불일치, 부서 직속, 방식 위반)
  - 통합
    - 부서 이름 유일, 부서 안 팀 이름 유일, 과정당 한 팀, `assignment_scope` CHECK, 직원·신청 팀 저장 왕복
    - 팀 삭제 이동(직원·처리된 신청·과정)과 409, 승인 시 팀 조정(다른 부서 팀 허용), 시드 멱등·운영 거부
  - API: 부서·팀·과정 담당 팀·직위·직원 관리, 신청 선택지와 규칙 오류 코드, 승인 `team_id`
- **로컬 검사 (compose `api`):** ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 861 passed.
- **프론트엔드:** 다시 만든 타입으로 `typecheck` 통과

## 남은 작업
- FE-1c(#78): 부서 → 팀 선택과 직위별 담당 선택 화면(Figma 먼저)
- FE-16: 팀·과정 담당 팀·직위 담당 방식 관리 화면
- 개발 DB의 기존 부서 `교육 1팀`(마이그레이션 전 하위 부서)은 그대로 남아 있다. 대기 중 신청 1건이 이 부서를 가리킨다. FE-1c에서 다시 신청하면 된다.
