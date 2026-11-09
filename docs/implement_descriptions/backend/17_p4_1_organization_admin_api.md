# 17. P4-1 조직(부서·직위·직원) 관리 API

- 상태: 완료 (2026-11-09 병합)
- 관련 PR: #20
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P4 (P4-1)
- 이전 기록: [16. P3-3b 회원 역할 관리 API](16_p3_3b_user_role_api.md)

## 배경
P3까지는 부서·직위를 테스트 데이터로만 만들 수 있었다. 운영진 가입 신청 폼의 선택지, 담당자 배정 화면의 직원 목록에는 실제 조직 데이터가 필요하다. 최고 관리자(`org.manage`)가 부서·직위를 관리하고 직원을 이동시킬 수 있게 한다. 학사 마스터(HRD·과정·기수)는 P4-2에서 만든다.

사용자가 실제 Google 로그인(구현 기록 11의 남은 작업)이 동작하는 것을 확인했다(2026-11-09).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `organization/domain/entities.py` | `Department.update`, `EmployeePosition.update` (생성 때와 같은 검증) |
| `core/persistence.py` | 공통 `delete`: 참조 중이면(ON DELETE RESTRICT) 409 `in_use` |
| `core/errors.py` | 서비스가 미리 검사하지 못한 DB 제약 위반(동시 요청 경합)을 409 `conflict`로 응답하는 전역 핸들러 |
| `organization/.../repositories.py` | 부서 (상위, 이름) 조회, 직위 이름 조회, 부서별 직원 페이지 |
| `organization/application/org_service.py` | `OrganizationAdminService`. 부서: 상위 안 이름 유일, 상위 존재, 여러 단계 순환 금지. 직위: 이름 유일. 직원: 조회·이동. 모든 변경에 감사 로그(전후) |
| `organization/presentation/org_router.py` | `GET·POST /admin/departments`, `PATCH·DELETE /admin/departments/{id}`, 직위도 같은 모양, `GET /admin/employees`(페이지·부서 필터), `GET·PATCH /admin/employees/{id}` |
| `tests/` | 수정 검증, 409 매핑, 삭제 `in_use`, 조회 메서드, 서비스(실제 DB: 트리 규칙·순환·이동·삭제·감사 로그, 직위, 직원 이동), API(CRUD 흐름, `parent_id: null` 이동, 409·422·404, 권한 403·401) |

## 주요 결정
- 직원은 가입 승인(P3-2b)으로만 만든다. 관리 API에는 조회와 부서·직위·고용 형태 이동만 둔다. 직원 삭제는 담당자 이력과 감사 추적을 위해 두지 않는다. 퇴사 처리는 필요해지면 계정 비활성화로 다룬다.
- 삭제는 하드 삭제지만, 참조 중이면 DB의 RESTRICT가 막고 409 `in_use`로 알려 준다. 하위 부서가 있거나 직원·가입 신청이 쓰는 부서·직위가 이에 해당한다.
- PATCH는 보낸 필드만 바꾼다. 부서 `parent_id`는 보내지 않으면 그대로이고, `null`을 보내면 최상위로 옮긴다(`model_fields_set`으로 구분).
- 부서 순환은 새 상위에서 위로 올라가며 자기 자신을 만나는지 확인한다. 부서 수가 적어 전체를 한 번 읽는다.
- 서비스가 먼저 중복을 검사한다(409 `department_name_taken` / `position_name_taken`). 동시 요청 경합으로 DB 유일 제약에 걸리면 전역 핸들러가 409 `conflict`로 응답한다.

## 발견한 문제와 해결
- 부서 PATCH의 "보내지 않음" 표시용 객체가 `dataclasses.asdict()`의 깊은 복사로 새 객체가 되면서 `is` 비교가 깨졌다. 그래서 수정하지 않은 필드에 그 객체가 그대로 들어갔다. `asdict` 대신 필드를 직접 읽도록 고쳤다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **255개 통과**
- 커밋 3개를 각각 워크트리로 꺼내 같은 검사 통과
- GitHub Actions (PR #20, run 42547005293): backend 잡 통과
- 사용자 확인: P4 진행 지시에 따라 CI 통과 후 병합

## 남은 작업
- P4-2: HRD 과정·회차, 운영과정, 기수 관리 API
