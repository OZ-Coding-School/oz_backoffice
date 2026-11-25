# 101. 멘토 단건 조회 (BE-3u)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #161
- 관련 결정: `docs/decisions.md` A102 (F79)
- 이전 기록: [100. 멘토 단위 배정 조회 (BE-3t)](100_mentor_assignments.md)

## 배경
FE-18a 멘토 상세 페이지의 머리(활성·신청 받기)와 계정 칸(이메일·휴대폰·가입)에 쓸 값이 프로필 응답에 없다. 목록을 검색해 찾는 우회 대신 단건 조회를 더한다(A102).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `educator/application/mentor_profiles.py` | `summary(mentor_id)`: 멘토 + 계약 수, 없으면 404 `mentor_not_found` |
| `educator/presentation/mentor_router.py` | `GET /admin/mentors/{mentor_id}`(`educator.mentor.read`): 목록 항목과 같은 `MentorListItem`. 목록과 단건이 항목 만들기(`_list_items`)를 함께 쓴다 |
| `tests/api/test_mentor_profile.py` | 단건이 목록 항목과 같음, 없는 멘토 404, 권한 없으면 403 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A102)
- 멘토 단건 조회 API를 백엔드 보완 PR로 먼저 더한다. 응답은 목록 항목과 같다.

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 913 passed

## 남은 작업
- FE-18a 멘토 목록·상세.
