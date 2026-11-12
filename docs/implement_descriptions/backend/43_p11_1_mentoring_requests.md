# 43. P11-1 멘토링 신청·시간 보류·조회·승인 전 취소·대기 만료

- 상태: 완료 (2026-11-12 병합)
- 관련 PR: #48
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P11 (P11-1)
- 이전 기록: [42. 멘토링 유형(평시/프로젝트) 제거](42_remove_mentoring_period_type.md)

## 배경
P11은 PR 3개로 나눴다(A42). 이번 PR은 그 첫 번째로, 수강생이 멘토링을 신청하면 시간 계좌에서 신청 시간을 **보류(HOLD)** 하고, 승인 전에 취소하거나 승인 기한이 지나면 **돌려준다(RELEASE)**. 승인·반려·세션 생성은 P11-2, 승인 후 취소·운영진 취소·변경과 다른 기능 연동은 P11-3에서 한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/request.py` | `MentoringRequest`: 주제(100자)·상세(필수 2,000자)·희망 일시 1~3(30분 경계, UTC, 서로 겹치지 않음)·신청 시간(30분 단위, 최대 120분) 검증, 승인 가능한 희망 일시·대기 만료 판정, 사유 필수 취소 |
| `mentoring/domain/balance.py` | `BalanceAccount.hold` / `release` (원장 항목에 `request_id`) |
| `mentoring/infrastructure/models/request.py`, 마이그레이션 17 | `mentoring_requests` 테이블, 원장 `request_id` FK, `replaced_request_id` 자기 참조 FK(raw SQL) |
| `mentoring/infrastructure/repositories.py` | 신청 리포지토리: 잠금, 대기 수 집계, 수강생(1:1 + 소속 팀)·멘토·기수별 목록, 만료 대상 조회 |
| `mentoring/application/availability_service.py` | `times_for`: 조회자 검사 없이 신청 가능 구간 계산 (신청 검증용) |
| `mentoring/application/request_service.py` | `MentoringRequestService`: 신청·승인 전 취소·대기 만료·목록 |
| `mentoring/presentation/request_router.py` | API (아래) |
| `workers/tasks/mentoring.py` | `mentoring.requests.expire` 작업 (10분마다) |

**API**

| 대상 | 메서드·경로 | 내용 |
| --- | --- | --- |
| 수강생 | `POST /api/v1/mentoring/requests` | 1:1은 `cohort_id`·`mentor_id`, 팀은 `team_id`(팀 담당 멘토에게) |
| 수강생 | `POST /api/v1/mentoring/requests/{id}/cancel` | 승인 전 취소, 신청자만, 사유 필수(300자) |
| 수강생 | `GET /api/v1/me/mentoring/requests?status=` | 본인 1:1 + 소속 팀 신청 |
| 멘토 | `GET /api/v1/me/mentor-requests?status=` | 받은 신청 |
| 운영진 | `GET /api/v1/admin/cohorts/{cohort_id}/mentoring/requests?status=&mentor_id=` | `mentoring.request.read`(기수 범위). 멘토 실명 포함 |

수강생·멘토 응답에는 멘토 표시 이름만 있고, 운영진 응답에만 멘토 실명(`mentor_name`)이 있다. 목록은 `limit`(최대 100)·`offset` 페이지네이션이다.

## 주요 결정 (사용자 결정, A42)
- 신청 시간은 기수 진행 단위의 배수이고 최대 120분이다. 희망 일시는 각각 신청 가능 구간 안이어야 하고 서로 겹치지 않아야 한다. 다른 사람의 대기 신청과는 겹쳐도 된다.
- 대기 신청 수 제한(`max_pending_requests`)은 1:1은 수강생당, 팀은 팀당이다.
- 팀 신청은 팀원 누구나 하고, 취소는 신청자만 한다. 팀 신청은 팀원 모두 조회한다.
- 반려·취소 사유는 필수다.
- 대기 만료: 승인 가능한 희망 일시가 남지 않은 대기 신청은 주기 작업이 취소하고(사유 "승인 기한 지남") 시간을 돌려준다.

## 구현 세부
- **검증 순서:** 신청자 확인(수강 중인 그 기수 수강생 / 팀원) → 기수 설정·허용 방식(1:1·팀) → 진행 단위 → 신청 가능 구간(멘토 신청 받기 꺼짐이면 `mentor_not_accepting`) → (트랜잭션) 계좌 잠금 → 계좌 사용 기간 → 대기 수 → 보류.
- **잠금 순서:** 계좌 → 신청 (하네스 §4). 취소·만료는 신청을 읽은 뒤 계좌와 신청을 이 순서로 잠그고, 잠그는 사이 상태가 바뀌었으면 건너뛴다.
- **만료 작업:** 멱등이다. 이미 취소된 신청은 대상이 아니라 여러 번 돌아도 결과가 같다. 신청 가능 구간 계산의 세션 제외(`BusySchedule`)는 세션이 생기는 P11-2·P11-3에서 붙인다(지금은 `NoBusySchedule`).
- **조회 쿼리:** 목록 1회 + 개수 1회 + 이름 붙이기(수강생·팀·멘토·회원 각각 IN 쿼리 1회)로, 건수와 무관하게 쿼리 수가 일정하다.
- **에러 코드:** `balance_account_missing`, `insufficient_balance`, `desired_time_unavailable`, `desired_time_outside_validity`, `too_many_pending_requests`, `mentor_not_accepting`, `mentoring_mode_not_allowed`, `invalid_request_duration`, `request_target_required`, `student_not_enrolled`, `not_cohort_student`, `not_team_member`, `not_requester`.

## 대기 만료 주기
- 대기 만료 작업 주기는 **10분**이다. A42는 "주기 작업"으로만 정했고, 사용자가 변경 요청 없이 병합을 확인해 10분으로 유지했다.

## 검증
- 단위: 도메인 규칙 15개(경계값: 0·120·150분, 30분 경계, 겹침, 시간대, 사유), 서비스 7개(보류, 검증 규칙, 진행 단위·허용 방식·수강 상태, 대기 수·사용 기간, 팀 신청, 취소·만료 멱등, 멘토 목록)
- 통합(PostgreSQL): 저장·조회 왕복, CHECK 제약(상태별 필드, 희망 일시 순서), 목록 필터, 만료 대상 조회
- API: 신청 → 보류 확인 → 수강생·멘토·운영진 목록 → 취소(사유 누락 422, 남의 신청 403) → 반환 확인, 규칙 위반 코드, 비로그인 401·다른 기수 회원 403·수강생의 운영진 API 403·멘토 아님 404
- 작업: 작업 이름·스케줄·서비스 조립
- GitHub Actions (PR #48): backend 잡 통과, 705 passed
- 사용자가 작업 완료를 확인했다(2026-11-12)
- 전체 705 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 코드 커밋 3개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했다(695 → 702 → 705 passed)
- 마이그레이션 17: `upgrade` → `migrate`("No changes detected") → `downgrade -v 17` → `upgrade` 확인

## 남은 작업
- P11-2: 승인·반려·세션 생성(USING), 신청 가능 시간에서 세션 제외
- P11-3: 승인 후 취소·운영진 취소(환불 선택)·변경, 불가 시간 충돌·멘토 변화·수강 종료 연동
- 운영: 작업 모듈은 기존 `app.workers.tasks.mentoring`이라 모듈 목록 변경은 없다. 정기 작업 표에 추가했다(`docs/operations/production_notes.md`)
