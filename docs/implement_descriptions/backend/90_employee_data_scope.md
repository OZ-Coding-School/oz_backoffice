# 90. 직원 응답에 직위 데이터 범위 (BE-3j)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #140
- 관련 결정: `docs/decisions.md` A91 (A90 보완)
- 이전 기록: [89. 직원 목록 전체·최고 관리자 함께 수정 (BE-3i)](89_employee_list_all.md)

## 배경
FE-15f 직원 상세 패널은 '직위 · 데이터 범위'를 보여 준다. 데이터 범위는 직위 목록(`GET /admin/positions`, `org.position.read`)에만 있어서, 직원 조회 권한만 있는 운영진은 볼 수 없었다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `organization/presentation/org_router.py` | `EmployeeResponse.data_scope`: 직원 응답을 만들 때 직위 목록을 한 번 읽어 직위의 데이터 범위를 넣는다 |
| `tests/api/test_organization_admin.py`, `test_position_permissions.py` | 목록 응답의 기본값, 직위 데이터 범위를 바꾸면 직원 응답도 바뀜 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성, 기존 직원 테스트 데이터에 값 추가 |

## 주요 결정 (사용자 결정, A91)
- 선택지 API나 권한을 바꾸지 않고 직원 응답에 넣는다.

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과, `pytest` 892 passed
- 프론트엔드: `lint`, `format:check`, `typecheck`, 직원 테스트 통과
- GitHub Actions (PR #140): 백엔드·프론트엔드 검사와 E2E 통과

## 남은 작업
- FE-15f 조직 설정 > 직원, BE-3k 전체 회원 API
