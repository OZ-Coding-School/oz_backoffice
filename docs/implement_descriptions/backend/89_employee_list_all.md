# 89. 직원 목록 전체·최고 관리자 함께 수정 (BE-3i)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #139
- 관련 결정: `docs/decisions.md` A90 (A83·A87·A89 보완)
- 이전 기록: [88. 담당 역할 칸 제거·직원 수정에서 담당 지정 (BE-3h)](88_staff_assignments_without_role.md)

## 배경
FE-15f 조직 설정 > 직원(F66)은 직원을 부서·팀별로 묶어 보여 주고, 오른쪽 상세 패널의 수정 폼에서 최고 관리자도 함께 바꾼다. 기존 직원 목록은 한 번에 100명까지만 주고 응답에 최고 관리자 여부가 없어서 먼저 보완한다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `organization/domain/repositories.py`, `infrastructure/repositories.py` | `list_page` → `search(department_id, team_id, query)`: 페이지 없이 전체(가입 순) |
| `organization/application/org_service.py` | `list_employees`가 목록만 돌려준다 |
| `organization/presentation/org_router.py` | `GET /admin/employees` 응답을 `list[EmployeeResponse]`로, 응답에 `is_super_admin`. `PATCH`에 `is_super_admin`: 보내면 최고 관리자만(403 `super_admin_only`), 소속·직위·담당 변경과 최고 관리자 변경을 한 `UnitOfWork`에서 저장(마지막 1명을 끄면 409 `last_super_admin`으로 모두 되돌림). 다른 항목 없이 최고 관리자만 보내면 직원 수정 감사 기록을 남기지 않는다 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성. 기존 직원·담당자 화면은 무한 스크롤 대신 한 번에 받도록 맞춤(15f에서 바뀔 화면) |

## 주요 결정 (사용자 결정, A90)
- 백엔드 보완 PR을 먼저, 목록은 페이지 없는 배열 전체.
- 최고 관리자는 수정 폼 안의 항목이고, 직원 PATCH에서 함께 저장한다(두 API를 따로 부르지 않음).
- 전체 회원 API는 BE-3j로 미룸.

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 892 passed. 새 테스트: 직원 수정에서 최고 관리자 켜기·목록 표시, 권한 코드만 있으면 403, 마지막 1명을 끄면 409이고 같은 요청의 고용 형태 변경도 되돌림. 목록 테스트는 배열 응답으로 고침
- 프론트엔드: `lint`, `format:check`, `typecheck`, `vitest` 313 passed, `build`, 직원 E2E 통과
- GitHub Actions (PR #139): 백엔드·프론트엔드 검사와 E2E 통과

## 남은 작업
- FE-15f 조직 설정 > 직원, BE-3j 전체 회원 API
