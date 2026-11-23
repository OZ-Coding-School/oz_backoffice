# 76. 멘토 세션 목록 탭·기수 필터, 세션 기수 (BE-2k)

- 상태: 완료 (2026-11-23 병합)
- 관련 PR: #111
- 관련 결정: `docs/decisions.md` A77, F46 (A68·A76)
- 이전 기록: [75. 멘토 받은 신청 보완 (BE-2j)](75_mentor_request_cohort.md)

## 배경
FE-10 멘토 세션 시안은 목록에 다가오는·기록 미제출·지난 세션·전체 탭과 건수, 기수 필터를 두고, 상세 머리에 기수 이름을 보여 준다. 멘토 세션 목록은 상태와 시작 시각 범위만 거를 수 있어서, '아직 끝나지 않은 세션'이나 '시작했는데 기록이 없는 세션'을 한 번에 고를 수 없었다. 사용자는 백엔드 보완을 먼저 하기로 했다(A77).

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `mentoring/domain/session.py` | `SessionView`(upcoming·record_missing·past), 열린/닫힌 상태 묶음, `SessionQuery.view`·`now`·`cohort_id` |
| `mentoring/infrastructure/repositories.py` | 세션 목록에 탭 조건과 신청자 기수 필터, 멘토 상태별 수의 기수 필터, 탭별 수 `count_views_for_mentor` |
| `mentoring/application/session_service.py` | `counts_for_mentor(cohort_id=)`, `views_for_mentor` |
| `mentoring/presentation/session_router.py` | `GET /me/mentor-sessions`에 `view`·`cohort_id`, 응답 `view_counts`. 세션 응답에 `cohort_id`·`bootcamp_name`·`cohort_number` |
| `tests/fakes/mentoring.py` | 인메모리 저장소의 탭 조건·탭별 수 (기수는 보지 않음) |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts`, `src/features/sessions/test-utils.ts` | 생성 타입 갱신, 테스트 세션에 새 필드 |

### 탭 조건 (A77)
- `upcoming`: 예정·진행 중이고 끝 시각이 지금 이후
- `record_missing`: 예정·진행 중이고 예정 시작 시각이 지금이거나 이전(기록하면 완료·노쇼가 된다). 진행 중인 세션은 두 탭에 모두 보일 수 있다
- `past`: 완료·노쇼·취소
- 상태별 `counts`와 탭별 `view_counts`는 상태·탭 필터와 무관하고 기수 필터는 따른다

## 주요 결정 (사용자 결정, A77)
- 탭은 백엔드가 계산한다(프론트에서 시각으로 나누지 않는다).
- 기수 필터와 탭별 건수를 둔다. 건수는 기수 필터를 따른다(A76과 같음).
- 세션 응답에도 신청자 기수를 넣는다(수강생·멘토·운영진 공통).

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 899 passed (통합 테스트 포함)
  - 통합: 탭 조건(진행 중 세션은 다가오는·미제출 둘 다, 취소는 지난), 기수 필터, 탭별 수·상태별 수의 기수 필터
  - API: `view_counts`·세션 기수, `view=past`, 다른 기수, 잘못된 `view` 422
- 프론트엔드: `typecheck`, `lint`, `format:check`, `vitest` 219 passed

- GitHub Actions (PR #111): 백엔드·프론트엔드 검사·E2E 3개 통과
- 사용자가 병합을 확인했다(2026-11-23)

## 남은 작업
- FE-10a 멘토 세션 목록
