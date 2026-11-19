# 65. 신청 목록 상태 여러 개 필터와 상태별 건수

- 상태: PR 진행 중
- 관련 PR: #85
- 관련 결정: `docs/decisions.md` A67, F29 (FE-4a 탭 시안 유지)
- 이전 기록: [64. 신청 응답 보완: 단건 조회·확정 세션·취소 주체·차감 상태](64_request_response_supplement.md)

## 배경
FE-4a 신청 내역 시안의 탭은 4개다: `전체 5 · 승인 대기 2 · 승인 1 · 반려·취소 2`. 사용자는 시안대로 탭 4개에 건수를 붙이기로 했다(F29). 그런데 목록 API에는 두 가지가 없었다.
- 상태는 하나만 받아서 '반려·취소'를 한 번에 조회할 수 없었다.
- 응답의 `total`은 고른 상태의 건수뿐이라, 다른 탭의 건수를 알 수 없었다.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `mentoring/domain/repositories.py`, `infrastructure/repositories.py` | `list_for_participants`·`list_for_mentor`의 `status` → `statuses`(`status IN`). `count_statuses_for_participants`·`count_statuses_for_mentor`: 상태별 `GROUP BY` 한 번, 없는 상태는 0 |
| `mentoring/application/request_service.py` | `RequestList(items, total, counts)`. `list_mine`·`list_for_mentor`가 건수를 함께 돌려준다 |
| `mentoring/presentation/request_router.py` | `status` 쿼리를 여러 개 받는다. 응답 `RequestListPage` = 기존 페이지 + `counts`(PENDING·APPROVED·REJECTED·CANCELED) |
| `tests/fakes/mentoring.py` | 인메모리 리포지토리도 같은 방식으로 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 다시 만들었다(F19) |

### API

| API | 내용 |
| --- | --- |
| `GET /me/mentoring/requests?status=REJECTED&status=CANCELED` | 상태를 여러 개 받는다. 없으면 전체, 하나만 보내면 이전과 같다. 없는 값은 422 |
| `GET /me/mentor-requests?status=` | 멘토 목록도 같은 방식이다 |
| 두 목록 응답 | `counts`를 함께 보낸다. 상태 필터와 무관하게 그 목록 대상 전체의 상태별 건수다. `total`은 지금처럼 필터를 적용한 건수다 |

- 쿼리는 목록마다 한 번 늘어난다(상태별 `GROUP BY`).
  - 멘토 목록은 `(mentor_id, status)` 인덱스를 쓴다.
  - 수강생 목록은 기존 목록 조회와 같은 `requester_id`·`team_id` 인덱스를 쓴다.
- 별도 건수 API는 두지 않았다(사용자 결정).

## 주요 결정 (사용자 결정, A67)
- 탭 건수는 목록 응답의 `counts`로 받는다.
- '반려·취소'는 `status`를 여러 개 보내 조회한다(묶음 값을 따로 두지 않음).
- 멘토가 받은 신청 목록에도 같이 적용한다(FE-9 대비).

## 발견한 문제와 해결
- 없음

## 검증
- **테스트**
  - 단위: 상태 여러 개 필터, 필터와 무관한 상태별 건수(수강생·멘토), 수강 등록이 없으면 모두 0
  - 통합: `status IN` 필터, `GROUP BY` 건수(없는 상태 0, 대상 없음)
  - API: `status` 두 개 조회, `counts`, 멘토 목록 `counts`, 없는 상태 값 422
- **로컬 검사 (compose `api`):** ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 879 passed.
- **프론트엔드:** 다시 만든 타입으로 `typecheck` 통과

## 남은 작업
- FE-4a: 신청 내역 목록·상세·취소 화면 (Figma 태블릿·모바일 먼저)
