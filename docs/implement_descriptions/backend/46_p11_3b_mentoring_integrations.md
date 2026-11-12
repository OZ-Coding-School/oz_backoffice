# 46. P11-3b 신청 연동 (불가 시간 충돌·멘토 변화·수강 종료)

- 상태: PR 진행 중
- 관련 PR: #51
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P11 (P11-3b)
- 이전 기록: [45. P11-3a 승인 후 취소·운영진 취소·변경](45_p11_3a_mentoring_cancel_change.md)

## 배경
P11의 마지막 PR이다. 앞선 PR에서 미뤄 둔 연동을 붙인다. 멘토·배정·팀·수강 상태가 바뀌거나 멘토가 불가 시간을 늘리면, 걸리는 대기 신청과 예정 세션을 자동으로 정리한다(A37·A39·A42·A45). P9에서 빈 목록을 주던 불가 시간 충돌 검사도 실제로 구현한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/application/request_cleanup.py` | `RequestCleanup`: 호출한 서비스의 트랜잭션 안에서 대기 신청 자동 취소·반려(RELEASE), 예정 세션 자동 취소(환불 선택). 조건 조회(`cancel_pending_where`·`count_pending_where`), 사유 상수 |
| `mentoring/application/schedule_conflicts.py` | `SessionScheduleConflicts`: 불가 시간 충돌 검사(`find`)·정리(`resolve`) |
| `mentoring/application/schedule_service.py` | 충돌 포트에 `resolve` 추가, confirm 저장 후 호출. 신청 받기 끄기 → 대기 신청 취소 |
| `mentoring/application/mentor_activation.py` | 멘토 비활성화: 미리보기에 취소될 대기 신청 수, 실행 때 취소 |
| `mentoring/application/assignment_service.py` | 기수 배정 비활성화·만료: 그 기수의 그 멘토 대기 신청 취소 |
| `mentoring/application/team_service.py` | 팀 담당 멘토 변경: 그 팀 대기 신청 취소. 팀원 제거: 그 팀원이 신청한 팀 대기 신청 취소 |
| `mentoring/application/enrollment_ended.py` | 수강 종료: 팀 이탈자의 팀 대기 신청·1:1 대기 신청 취소, 시작 전 1:1 예정 세션 환불 없이 취소, 그 뒤 잔여 회수 |
| `mentoring/infrastructure/repositories.py` | 신청 `list_pending`(멘토·기수·팀·신청자·1:1 조건), 세션 `list_upcoming` |
| `mentoring/presentation/cleanup.py` | 라우터용 `build_cleanup` |
| 라우터 | 응답에 취소 건수 (아래) |

**응답 변경 (A45: 바로 처리하고 취소 건수만 알림)**

| API | 추가 필드 |
| --- | --- |
| `DELETE /admin/cohorts/{cohort_id}/mentor-assignments/{id}` | `canceled_pending_requests` |
| `POST /admin/mentors/{mentor_id}/deactivate` | `pending_requests`(미리보기면 취소될 수, 실행이면 취소한 수). 안내 문구에도 표시 |
| `PUT /me/mentor-schedule/accepting`, `PUT /admin/mentors/{id}/schedule/accepting` | `canceled_pending_requests` |
| `PATCH /admin/cohorts/{cohort_id}/mentoring-teams/{id}`, `DELETE .../members/{student_id}` | `canceled_pending_requests` |

## 주요 결정
- 기존 결정(A37·A42): 불가 시간 변경은 대기 신청의 희망 일시가 **모두** 막힐 때만 충돌, 세션은 겹치면 충돌. confirm하면 대기 신청은 반려(시간 해제), 세션은 취소(전액 환불). 멘토 비활성화·배정 비활성화(만료 포함)·신청 받기 끄기·팀 담당 멘토 변경 때 대기 신청은 자동 취소, 승인 세션은 유지. 수강 종료 때 대기 신청 취소, 1:1 예정 세션 환불 없이 취소, 팀 세션 유지.
- 사용자 결정(A45): 수강 종료 때 취소하는 1:1 세션은 **아직 시작 전인 것만**. **팀에서 빠진 신청자의 팀 대기 신청은 자동 취소**. 금지 시간대·추가 휴일 추가는 기존 건에 **영향 없음**. 자동 취소는 **바로 처리하고 응답에 건수만**.

## 구현 세부
- **트랜잭션:** 자동 정리는 원인 변경과 같은 트랜잭션에서 한다. 하나라도 실패하면 원인 변경도 되돌아간다. 잠금은 계좌(id 순) → 신청 → 세션이고, 잠그는 사이 상태가 바뀐 건은 건너뛴다(멱등).
- **"승인할 수 있는 희망 일시":** 아직 시작 전인 희망 일시다. 하나라도 불가 시간에 걸리지 않으면 멘토가 그 일시로 승인할 수 있으므로 충돌이 아니다. 시작 전 희망 일시가 없는 신청은 대기 만료 작업이 처리한다.
- **불가 시간 충돌 범위:** 반복 불가 시간은 `occurrences`로 그 신청·세션 시각에 걸리는 회차만 본다. 이미 시작한 세션은 대상이 아니다.
- **배정 비활성화 범위:** 신청자의 기수가 그 배정의 기수인 대기 신청만(1:1·팀 모두). 멘토 비활성화는 기수와 무관하게 그 멘토의 대기 신청 전부.
- **수강 종료 순서:** 팀에서 빼기 → 팀 이탈자의 팀 대기 신청 취소(팀 계좌로 반환) → 1:1 대기 신청 취소 → 시작 전 1:1 세션 취소(환불 없음, USING 유지) → 1:1 잔여 회수. 대기 신청에서 돌려받은 보류도 잔여가 되므로 함께 회수된다. 잔여가 0이고 보류만 있던 계좌도 대상에 넣는다.
- **감사 로그:** `mentoring.request.auto_cancel`·`auto_reject`, 원인 변경을 한 사람(작업이면 없음)을 기록한다.
- **사유:** "멘토 비활성화로 자동 취소", "기수 배정 종료로 자동 취소", "멘토가 신청 받기를 꺼 자동 취소", "팀 담당 멘토 변경으로 자동 취소", "신청자가 팀에서 빠져 자동 취소", "수강 종료로 자동 취소", "멘토 일정 변경"(반려·세션 취소).
- **알림:** 보류(M24).

## 검증
- 단위: 자동 정리(취소·반려·세션 환불/미환불·멱등·감사 actor), 신청 받기 끄기, 팀 멘토 변경·팀원 제거, 배정 비활성화·만료(그 기수만), 멘토 비활성화 미리보기 건수·실행, 수강 종료(1:1 대기·팀 이탈자 팀 대기 취소, 남은 팀원 신청 유지, 시작 전 1:1 세션 환불 없이 취소, 팀 세션 유지, 회수, 멱등), 불가 시간 충돌(일부 희망 일시만 막힘은 제외, 다른 멘토 제외, 반려·세션 취소·환불), 미리보기는 정리하지 않음
- 통합(PostgreSQL): `list_pending` 조건 조합, `list_upcoming`(시작 전·1:1만), 수강 종료 처리(새 조립)
- API: 신청 받기 끄기·배정 비활성화로 대기 신청 취소와 잔여 반환, 불가 시간 미리보기 충돌 목록 → confirm → 반려·세션 취소·전액 환불
- 전체 736 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 코드 커밋 4개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했다(729 → 733 → 734 → 736 passed)
- 스키마 변경 없음

## 남은 작업
- P12: 승인 후 Meet Space 생성, 취소 시 Space 정리
- 알림 방식(M24) 확정 후 자동 취소·반려 알림
