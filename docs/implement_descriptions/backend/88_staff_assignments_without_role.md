# 88. 담당 역할 칸 제거·직원 수정에서 담당 지정 (BE-3h)

- 상태: PR 진행 중
- 관련 PR: (작성 중)
- 관련 결정: `docs/decisions.md` A88·A89 (A63·A83 변경)
- 이전 기록: [87. 직위 = 역할, 최고 관리자 필드, 데이터 범위 (BE-3g)](87_positions_as_roles.md)

## 배경
직위가 곧 역할이 되면서(A87) 담당자 행의 역할 칸(운영 매니저·조교)은 의미가 없어졌다. 담당은 과정 담당인지 기수 담당인지만 구분하고, 직원 정보를 수정할 때 직위의 담당 방식대로 지정한다(A88·A89).

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `organization/domain/enums.py`, `entities.py`, `registration.py` | `StaffRole` 삭제. 담당 1건은 과정 또는 기수. 신청 규칙은 직위 방식만 보고, 기수 담당은 기수 담당자가 이미 있는 기수 제외(A63). `check_employee_assignments`: 과정 방식은 과정 여러 개, 기수 방식은 기수 하나, 없으면 담당 없음 |
| `organization/infrastructure/models.py`, `repositories.py`, `migrations/models/32_*` | `bootcamp_staffs`·`cohort_staffs`·`employee_registration_assignments`의 `role` 삭제, 유일 제약을 (직원, 과정)·(직원, 기수)·(신청, 과정, 기수)로. `staffed_cohort_ids` |
| `organization/application/org_service.py` | 직원 수정에 `bootcamp_ids`·`cohort_ids`(보내면 통째로 교체): 직위 방식 검사, 다른 직원의 기수 제외, 담당 가능 검사, 감사 로그 `organization.employee.assignments` |
| `organization/presentation/org_router.py` | `PATCH /admin/employees/{id}`: 소속·직위는 `org.employee.manage`, 담당은 `staff.assignment.manage`(둘 중 하나가 있어야 들어오고, 보낸 항목마다 검사). 응답 담당에서 역할 제거 |
| `organization` 담당자 API·신청 API | 요청·응답의 `role`, 선택지의 `staff_roles` 제거 |
| `docs/database_schema_v2.dbml` | 역할 칸·`StaffRole` 제거 |
| `apps/frontend` | 생성 타입, 운영진 정보 입력·승인 폼 본문, 신청 상태 화면 배지('과정'·'기수'), 담당자 추가 창의 역할 선택·담당자 표의 역할 열 제거, 테스트 데이터 |

## 주요 결정 (사용자 결정, A88·A89)
- 직원 수정에 담당 포함(통째로 교체), 직위의 담당 방식을 따름, 과정·기수 담당자 API는 그대로 두되 역할 칸만 제거, 신청 담당도 역할 없이 과정·기수만.

## 발견한 문제와 해결
- 역할 컬럼을 지우면 신청 담당의 유일 인덱스(역할 포함)도 함께 지워져, (신청, 과정, 기수) 유일 인덱스를 다시 만들었다. 되돌리면 역할 칸은 MANAGER로 채운다(예전 값은 없다).
- Playwright 첫 실행에서 멘토 일정 시나리오가 시간 초과로 흔들렸고 다시 실행하면 모두 통과했다(이번 변경과 무관).

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 891 passed (통합 포함). 새 테스트: 담당 지정 규칙(단위), 직원 수정의 담당(과정 여러 개·기수 하나·직위 변경과 함께 교체·다른 직원의 기수·해제), 항목별 권한(API)
- 마이그레이션: `aerich upgrade` → `migrate`(No changes) → `downgrade -v 32` → `upgrade`, DBML 파서 검증
- 프론트엔드: `lint`, `format:check`, `typecheck`, `vitest` 304 passed(UTC·Asia/Seoul), `build`, Playwright E2E 39 passed

## 남은 작업
- FE-15d 조직 설정 모듈 + 권한 화면, 이후 직원 화면에서 직위·최고 관리자·담당 지정(F64)
