# 75. 멘토 받은 신청 보완: 기수·수강 상태·기수 필터 (BE-2j)

- 상태: PR 진행 중
- 관련 PR: #108
- 관련 결정: `docs/decisions.md` A76, F43 (A67 보완)
- 이전 기록: [74. 세션 목록 정렬 (BE-2i)](74_session_list_order.md)

## 배경
FE-9 멘토 받은 신청 시안은 목록·상세에 신청자의 기수 이름(예: 백엔드 12기)과 수강 상태(수강 중)를 보여 주고, 목록 오른쪽에 기수 필터를 둔다. 신청 응답에는 이 정보가 없었고, 받은 신청 목록은 기수로 거를 수 없었다. 사용자는 기수·수강 상태와 기수 필터만 보완하기로 했다. 희망 일시별 겹침은 응답에 넣지 않고 승인할 때 409로 안내한다(A76).

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `mentoring/presentation/presenters.py` | `Names`에 신청자 기수·수강 상태(학생 조회에서 함께 얻음), `NameBook.cohort_labels`(academy `cohort_labels`, IN 쿼리 한 번) |
| `mentoring/presentation/request_router.py` | 신청 응답에 `cohort_id`·`bootcamp_name`·`cohort_number`·`requester_status`. `GET /me/mentor-requests`에 `cohort_id` |
| `mentoring/application/request_service.py` | `list_for_mentor(cohort_id=)`. 건수도 기수 필터를 따른다 |
| `mentoring/domain/repositories.py`, `infrastructure/repositories.py` | 멘토 목록·건수에 신청자 기수 필터(`requester__cohort_id`) |
| `tests/fakes/mentoring.py` | 인메모리 저장소 인자 맞춤 (기수는 보지 않음) |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts`, `src/features/requests/test-utils.ts` | 생성 타입 갱신, 테스트 신청에 새 필드 |

## 주요 결정 (사용자 결정, A76)
- 기수·수강 상태는 수강생·멘토·운영진 공통 신청 응답에 넣는다.
- 상태별 건수(`counts`)는 상태 필터와는 무관하고 기수 필터는 따른다. 탭 숫자가 고른 기수의 목록과 맞는다.
- 희망 일시별 겹침은 넣지 않는다. 승인할 때 겹치면 기존대로 409다(A43).

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 898 passed (통합 테스트 포함)
  - 통합: 멘토 목록·건수의 기수 필터 (다른 기수 신청 제외, 없는 기수는 0)
  - API: 응답의 기수·수강 상태, `cohort_id` 필터의 total·counts
- 프론트엔드: `typecheck`, `lint`, `format:check`, `vitest` 208 passed

## 남은 작업
- FE-9a 멘토 받은 신청 목록
