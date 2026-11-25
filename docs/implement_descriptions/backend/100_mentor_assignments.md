# 100. 멘토 단위 배정 조회 (BE-3t)

- 상태: PR 진행 중
- 관련 PR: #160
- 관련 결정: `docs/decisions.md` A101 (F79, A35)
- 이전 기록: [99. 멘토 목록 보완 (BE-3s)](99_mentor_list_fields.md)

## 배경
FE-18a 멘토 상세의 배정 탭은 한 멘토의 모든 기수 배정을 카드로 보여 준다(F79). 운영진 배정 API는 기수 단위뿐이라 멘토 단위 조회를 더한다(A101).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `mentoring/application/assignment_service.py` | `list_by_mentor`: 없는 멘토는 404 `mentor_not_found`, 비활성 포함 |
| `mentoring/presentation/assignment_router.py` | `GET /admin/mentors/{mentor_id}/mentor-assignments`(`educator.mentor.read`): 본인 배정 조회와 같은 응답(정산 조건·비활성 사유 + 운영과정 이름·기수 번호), 활성 먼저·최근 시작부터 |
| `tests/api/test_mentor_assignments.py` | 활성·비활성 순서, 비활성 사유, 없는 멘토 404 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A101)
- 멘토 단위 배정 조회 API를 따로 둔다. 권한은 멘토 목록과 같은 `educator.mentor.read`.

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 913 passed

## 남은 작업
- FE-18a 멘토 목록·상세.
