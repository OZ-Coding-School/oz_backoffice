# 105. 운영진 멘토별 세션 조회 (BE-3y)

- 상태: PR 진행 중
- 관련 PR: #170
- 관련 결정: `docs/decisions.md` A106 (F85)
- 이전 기록: [104. 가입 전 멘토의 가입 연결 (BE-3x)](104_pending_mentor_signup.md)

## 배경
FE-18c-2 일정 대리는 멘토 일정 화면(FE-11)을 운영진 API로 재사용한다. 시간표에 그 주의 세션을 그려야 하는데 운영진 세션 목록은 기수별로만 있어 멘토 한 명의 세션을 기간으로 조회하는 API를 더한다(A106).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `mentoring/application/session_service.py` | `list_by_mentor`: 없는 멘토는 404, 멘토 세션 저장소 조회 재사용 |
| `mentoring/presentation/session_router.py` | `GET /admin/mentors/{mentor_id}/sessions`(`educator.mentor.read`): 멘토 본인 목록과 같은 필터·응답 |
| `api/v1.py` | 라우터 등록 |
| `tests/api/test_mentoring_requests.py` | 기간·상태 필터, 없는 멘토 404, 권한 없으면 403 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A106)
- 일정 대리 시간표에 세션을 보여 주기 위해 백엔드를 먼저 보완한다.

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 922 passed

## 남은 작업
- FE-18c-2 일정 대리.
