# 91. 부서·팀 직원 수 (BE-3k)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A92
- 이전 기록: [90. 직원 응답에 직위 데이터 범위 (BE-3j)](90_employee_data_scope.md)

## 배경
FE-15g 조직 설정 > 부서는 목록·조직도에 부서·팀별 직원 수를 보여 주고, 팀을 지울 때 직원이 있다고 안내한다. 부서·팀 응답에 직원 수가 없어서 먼저 더한다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `organization/domain/repositories.py`, `infrastructure/repositories.py` | `count_by_org()`: 직원의 (부서, 팀)을 한 번 읽어 부서별·팀별 수 |
| `organization/application/org_service.py` | `employee_counts()` |
| `organization/presentation/org_router.py` | `DepartmentResponse.employee_count`(팀 없는 직원 포함), `TeamResponse.employee_count`. 목록·수정 응답에 채우고, 만들 때는 0 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A92)
- 부서·팀 응답에 직원 수를 넣는다. 전체 회원 API는 BE-3l로 미룸.

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과, `pytest` 892 passed (팀이 없는 직원은 부서에만 세는지, 팀으로 옮기면 팀 수가 느는지)
- 프론트엔드: `lint`, `typecheck`, `vitest` 321 passed

## 남은 작업
- FE-15g 조직 설정 > 부서
