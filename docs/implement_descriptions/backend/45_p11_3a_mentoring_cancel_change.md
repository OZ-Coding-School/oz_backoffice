# 45. P11-3a 승인 후 취소·운영진 취소·변경

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P11 (P11-3a)
- 이전 기록: [44. P11-2 멘토링 승인·반려·세션 생성](44_p11_2_mentoring_approval.md)

## 배경
P11-3은 둘로 나눴다(A44). 이번 PR(P11-3a)은 승인된 신청의 취소(환불), 운영진 취소(환불 선택), 신청 변경을 붙이고, 신청 가능 시간 계산에서 멘토의 잡힌 세션을 뺀다. 불가 시간 충돌·멘토 변화·수강 종료 연동은 P11-3b에서 한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/request.py` | `cancel`을 승인된 신청까지 넓힘(`request_not_cancelable`), `ensure_before_deadline`(시작 `min_lead_hours` 전까지, `cancel_deadline_passed`) |
| `mentoring/domain/session.py` | `cancel`: 예정(SCHEDULED) 세션만 (`session_not_cancelable`) |
| `mentoring/domain/balance.py` | `refund`: 사용 → 잔여 (REFUND) |
| `mentoring/infrastructure/repositories.py` | 세션 `save`·`get_by_request`·`lock_by_request`·`busy`(멘토의 취소되지 않은 세션 구간, 변경 중인 신청 제외) |
| `mentoring/application/availability_service.py` | `BusySchedule`에 `exclude_request_id`, `times_for(..., exclude_request_id=)` |
| `mentoring/application/request_service.py` | 취소(대기·승인 후), `staff_cancel`, `change`. 신청 생성을 `_prepare`(트랜잭션 밖 검사)·`_place`(트랜잭션 안 보류·저장)로 나눠 변경과 함께 쓴다 |
| `mentoring/presentation/request_router.py` | API (아래) |
| `presentation/availability_router.py`, `workers/tasks/mentoring.py` | 바쁜 일정 = 세션 리포지토리 (`NoBusySchedule`은 단위 테스트용으로만 남김) |

**API**

| 대상 | 메서드·경로 | 내용 |
| --- | --- | --- |
| 수강생·멘토 | `POST /api/v1/mentoring/requests/{id}/cancel` `{reason}` | 대기: 신청자만, 보류 해제. 승인 후: 신청자·담당 멘토, 시작 `min_lead_hours` 전까지, 세션 취소 + 전액 환불 |
| 수강생 | `POST /api/v1/mentoring/requests/{id}/change` `{topic, detail, desired_times, duration}` | 신청자만. 201, 응답은 새 신청(`replaced_request_id` = 기존) |
| 운영진 | `POST /api/v1/admin/cohorts/{cohort_id}/mentoring/requests/{id}/cancel` `{reason, refund=true}` | `mentoring.request.cancel`(기수 범위). 마감과 무관 |

계획 문서의 운영진 취소 경로(`/admin/mentoring/requests/{id}/cancel`)는 다른 운영진 API와 같이 기수 범위 권한을 검사하도록 `/admin/cohorts/{cohort_id}/...`로 두었다.

## 주요 결정
- 사용자 결정(A44): PR 분할(3a·3b). 운영진이 **대기 신청을 취소하면 환불 선택과 무관하게 보류 해제**하고, 환불 선택은 승인된 신청에만 적용한다(환불 안 함이면 USING 유지). 운영진은 **예정(SCHEDULED) 세션만** 취소한다(시작이 지났어도 기록 전이면 가능). 변경은 **같은 대상**(멘토, 1:1/팀)에서 희망 일시·신청 시간·주제·상세만 바꾸고, 새 신청은 신청과 같은 검사를 모두 통과해야 한다.
- 기존 결정: 승인 후 취소는 수강생·멘토가 시작 `min_lead_hours` 전까지, 전액 환불(M26). 취소·변경은 신청자만(A42, 팀도 신청자만). 사유 필수(A42).

## 구현 세부
- **변경의 원자성:** 새 신청의 설정·진행 단위·신청 가능 구간 검사는 트랜잭션 전에 끝낸다. 트랜잭션 안에서 기존 신청을 취소(RELEASE 또는 세션 취소 + REFUND)한 뒤 새 신청의 사용 기간·대기 수·보류를 검사한다. 여기서 실패하면(예: 잔여 부족) 트랜잭션이 되돌아가 기존 신청·세션이 그대로 남는다(API 테스트로 확인). 대기 수는 기존 신청을 취소로 저장한 뒤에 세므로 기존 대기 신청은 세지 않는다.
- **변경 때 신청 가능 시간:** 기존 신청의 세션은 바쁜 일정에서 빼고 계산해, 같은 시각을 다시 고르거나 겹치게 옮길 수 있다.
- **마감 검사 위치:** 잠근 세션의 시작 시각으로 트랜잭션 안에서 본다.
- **운영진 취소 범위:** 신청자의 기수가 경로의 기수와 다르면 404다.
- **잠금 순서:** 계좌 → 신청 → 세션.
- **신청 가능 시간:** 세션(취소 제외)을 바쁜 일정으로 넣어 신청 가능 구간에서 뺀다(A38에서 미룬 것).
- **에러 코드:** `not_request_party`(승인 후 취소 권한), `cancel_deadline_passed`, `request_not_cancelable`, `session_not_cancelable`.
- **알림:** 보류(M24).

## 검증
- 단위: 도메인(승인 후 취소, 마감 경계: 정확히 24시간 전 허용·1분 늦으면 거부, REFUND, 예정 세션만 취소), 서비스(승인 후 취소: 권한·마감·멘토 취소·환불, 운영진 취소: 다른 기수 404·환불 안 함·대기 해제·완료 세션 거부, 변경: 멘토 거부·같은 시각 재선택·REFUND → HOLD·검사 실패 시 기존 유지)
- 통합(PostgreSQL): 세션 요청별 잠금·저장, 바쁜 구간(정렬·제외·취소 제외)
- API: 잡힌 세션이 신청 가능 시간에서 빠짐, 변경이 트랜잭션 안에서 실패하면 기존 신청·세션 유지, 멘토 변경 403, 변경 성공(새 신청·기존 세션 취소·잔여), 운영진 취소(수강생 403, 환불 안 함 → 사용 유지, 두 번 취소)
- 전체 725 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 코드 커밋 4개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했다(720 → 721 → 724 → 725 passed)
- 스키마 변경 없음

## 남은 작업
- P11-3b: 불가 시간 충돌 처리(대기 신청 반려·세션 취소 환불), 멘토 비활성화·배정 비활성화·신청 받기 끄기·팀 멘토 변경 시 대기 신청 취소, 수강 종료 시 대기 신청 취소·1:1 예정 세션 취소(환불 없음)
- P12: Meet Space 생성(승인 후), 취소 시 Space 처리
