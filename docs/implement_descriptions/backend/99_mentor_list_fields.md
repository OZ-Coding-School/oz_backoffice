# 99. 멘토 목록 보완 (BE-3s)

- 상태: PR 진행 중
- 관련 PR: #159
- 관련 결정: `docs/decisions.md` A100 (F79, A37)
- 이전 기록: [98. 수강생 상세 API (BE-3r)](98_student_detail.md)

## 배경
FE-18a 강사·멘토 > 멘토 목록 표에 활성 배정 기수와 신청 받기를 보여 준다(F79). 운영진 멘토 목록 응답에 없어 더한다(A100).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `educator/application/mentor_cohorts.py` | `MentorCohort`·`MentorCohortReader` 포트 |
| `app/composition/mentor_cohorts.py` | `MentorCohortComposer`: 멘토 여러 명의 활성 배정(한 번에) + 기수·운영과정 이름 |
| `mentoring/infrastructure/repositories.py` | `TortoiseCohortMentorRepository.list_active_by_mentors` (최근 시작부터) |
| `educator/presentation/mentor_router.py` | `GET /admin/mentors` 항목에 `accepting_requests`·`active_cohorts` |
| `main.py` | `app.state.mentor_cohorts` 배선(B10) |
| `tests/api/test_mentor_profile.py` | 신청 받기·활성 배정 기수(비활성 배정 제외) |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A100)
- 기존 목록 응답에 더한다. 배정·기수 이름은 조합 모듈에서 모은다.

## 발견한 문제와 해결
- 테스트에서 비활성 배정을 `is_active=False`로 바로 만들면 비활성 시각·사유 CHECK에 걸려 도메인 `deactivate`로 만들었다.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 912 passed

## 남은 작업
- FE-18a 멘토 목록·상세.
