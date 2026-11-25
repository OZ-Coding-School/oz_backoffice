# 92. 부서·팀·직위 영향 조회 (BE-3l)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #143
- 관련 결정: `docs/decisions.md` A93
- 이전 기록: [91. 부서·팀 직원 수 (BE-3k)](91_org_employee_counts.md)

## 배경
부서·팀 삭제, 팀의 부서 이동, 직위 권한 저장, 직위 삭제·담당 방식·데이터 범위 변경 때 확인 창이 '직원 N명' 같은 글 대신 실제로 영향받는 대상을 목록으로 보여 주기로 했다(A93). 팀·직위를 쓰는 운영진 가입 신청은 조회할 API가 없었고, 직원 목록은 직원 조회 권한이 있어야 해서 영향 조회 API를 따로 만든다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `organization/application/impact.py` | `OrgImpactQueries`: 부서(직원·신청·팀), 팀(직원·신청·담당 과정), 직위(직원·신청). 없으면 404 |
| `organization/domain/repositories.py`, `infrastructure/repositories.py` | 직원 검색에 `position_id`, 가입 신청 `list_referencing(department_id·team_id·position_id)`(상태 무관) |
| `organization/presentation/org_router.py` | `GET /admin/departments|teams|positions/{id}/impact` → `OrgImpactResponse`(employees·registrations·teams·bootcamps, 이름으로 풀어서). 부서·팀은 `org.department.manage`, 직위는 `org.position.manage` 또는 `access.role.manage` |
| `presentation/dependencies.py` | `get_org_impact_queries` |
| `tests/fakes/organization.py` | 메모리 신청 저장소에 `list_referencing` |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A93)
- 영향 목록은 백엔드 영향 조회 API로 가져온다(화면에서 다른 목록을 거르지 않음).
- 전체 회원 API는 BE-3m으로 미룸.

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과, `pytest` 894 passed (새 테스트: 팀·부서·직위 영향 목록, 없는 팀 404, 권한)
- 프론트엔드: `lint`, `typecheck` 통과
- GitHub Actions (PR #143): 백엔드·프론트엔드 검사와 E2E 통과

## 남은 작업
- FE-15g 조직 설정 > 부서(삭제·이동 확인 창), 권한 화면 저장 확인 창, FE-15h 직위
