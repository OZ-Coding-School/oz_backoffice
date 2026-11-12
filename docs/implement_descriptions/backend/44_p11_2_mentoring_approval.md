# 44. P11-2 멘토링 승인·반려·세션 생성

- 상태: PR 진행 중
- 관련 PR: #49
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P11 (P11-2)
- 이전 기록: [43. P11-1 멘토링 신청·시간 보류·조회·승인 전 취소·대기 만료](43_p11_1_mentoring_requests.md)

## 배경
P11의 두 번째 PR이다(A42). 멘토가 대기 신청의 희망 일시 하나를 골라 승인하면 보류한 시간을 사용으로 옮기고(USING) 세션을 만든다. 반려하면 보류를 돌려준다(RELEASE). 만들어진 세션을 수강생·멘토·운영진이 조회한다. 승인 후 취소·운영진 취소·변경과 다른 기능 연동은 P11-3에서 한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/request.py` | `approve(starts_at, now)`: 희망 일시 중 하나·시작 전, (시작, 종료) 반환. `reject(reason, now)`: 사유 필수 |
| `mentoring/domain/balance.py` | `use`: 보류 → 사용 (USING) |
| `mentoring/domain/session.py` | `MentoringSession`, 자동 제목 `session_title`, 목록 조건 `SessionQuery` |
| `mentoring/infrastructure/models/session.py`, 마이그레이션 18 | `mentoring_sessions`: 신청 하나에 세션 하나(유니크), 상태·녹화 상태·시간 범위 CHECK, **멘토 일정 겹침 EXCLUDE**(취소 제외) |
| `mentoring/infrastructure/repositories.py` | 세션 리포지토리: EXCLUDE 위반 → 409, 회차 수, 신청자 일정 겹침, 참여자·멘토·기수별 목록 |
| `mentoring/application/approval_service.py` | `MentoringApprovalService`: 승인·반려 |
| `mentoring/application/session_service.py` | `MentoringSessionQueries`: 세션 목록·단건 |
| `mentoring/presentation/presenters.py` | 신청·세션 응답에 이름 붙이기(신청자·팀·멘토 표시 이름·실명). P11-1 신청 API에서 분리(refactor 커밋) |
| `mentoring/presentation/request_router.py`, `session_router.py` | API (아래) |

**API**

| 대상 | 메서드·경로 | 내용 |
| --- | --- | --- |
| 멘토 | `POST /api/v1/mentoring/requests/{id}/approve` `{starts_at}` | 그 신청의 멘토만. 응답은 신청 + 세션 |
| 멘토 | `POST /api/v1/mentoring/requests/{id}/reject` `{reason}` | 그 신청의 멘토만, 사유 필수(300자) |
| 수강생 | `GET /api/v1/me/mentoring/sessions` | 본인 1:1 + 소속 팀 세션 |
| 멘토 | `GET /api/v1/me/mentor-sessions` | 본인 세션 |
| 참여자 | `GET /api/v1/mentoring/sessions/{id}` | 1:1 신청 수강생·팀원·담당 멘토. 아니면 404 |
| 운영진 | `GET /api/v1/admin/cohorts/{cohort_id}/mentoring/sessions?mentor_id=` | `mentoring.request.read`(기수 범위), 멘토 실명 포함 |
| 운영진 | `GET /api/v1/admin/cohorts/{cohort_id}/mentoring/sessions/{id}` | 다른 기수 세션이면 404 |

목록 필터는 `status`, `from`(시작 시각 이상), `to`(시작 시각 미만)이고 시작 시각 최신순이다. 세션 응답에는 신청 상세 내용(`detail`)과 Meet 주소(`google_meet_url`, P12 전에는 null)가 있다.

## 주요 결정 (사용자 결정, A43)
- **승인 때 다시 보는 것:** 고른 희망 일시가 시작 전인지와 겹침만 본다. 멘토가 직접 고르므로 운영시간·불가 시간·금지 시간대·신청 마감은 다시 보지 않는다.
- **겹침:** 멘토 일정(DB EXCLUDE, 409 `mentor_schedule_conflict`)과 신청자 일정을 모두 막는다. 1:1은 그 수강생의 1:1 세션과 소속 팀 세션, 팀은 그 팀의 세션과 팀원 각자의 1:1 세션이 겹치면 409 `participant_schedule_conflict`(취소된 세션 제외).
- **세션 조회:** 목록과 단건 상세를 둔다.

## 구현 세부
- **세션 제목:** "신청자(팀 이름 또는 수강생 이름) · 멘토 표시 이름 멘토링 N회차"(A42). N은 같은 신청자(1:1은 수강생, 팀은 팀)·같은 멘토의 취소되지 않은 세션 수 + 1이다. 100자를 넘으면 앞부분을 줄이고 "멘토링 N회차"는 남긴다.
- **잠금과 직렬화:** 승인은 참여자(1:1은 수강생·소속 팀, 팀은 팀·팀원)의 계좌를 id 순서로 잠근 뒤 신청을 잠근다(계좌 → 신청 → 세션). 같은 참여자의 승인끼리 직렬화돼 신청자 겹침 검사가 경합에 빠지지 않는다. 계좌가 없는 팀원(1:1 시간 미지급)은 잠글 행이 없어 이 직렬화에서 빠지지만, 그 팀원은 1:1 신청을 할 수 없어 1:1 세션이 생기지 않는다.
- **멘토 일정 겹침:** 서비스가 따로 검사하지 않고 DB EXCLUDE에 맡긴다. 다른 멘토 승인과 동시에 일어나도 DB가 막는다. 이어지는 세션(종료 = 다음 시작)은 허용한다.
- **실패한 승인:** 겹침으로 거부되면 트랜잭션이 되돌아가 신청은 대기, 보류 시간은 그대로다.
- **세션 단건 권한:** 참여자·담당 멘토가 아니면 존재를 숨기려고 404를 준다(운영진은 기수 범위 API).
- **조회 쿼리:** 목록 1회 + 개수 1회 + 신청 1회 + 이름(수강생·팀·멘토·회원 각 1회)으로 건수와 무관하게 쿼리 수가 일정하다. 겹침 검사·회차 수는 신청과 조인한다(`request_id` 유니크 인덱스, 세션 `(mentor_id, starts_at)` 인덱스).
- **알림:** 승인·반려 알림은 보류(M24).

## 검증
- 단위: 도메인(승인: 희망 일시 아님·시간대 없음·시작 시각과 같음·두 번 승인, 반려 사유, USING, 제목 길이), 서비스 6개(승인·회차, 권한·규칙, 멘토/신청자 겹침과 실패 시 보류 유지, 팀원 1:1·팀 세션 겹침, 반려, 세션 조회 권한)
- 통합(PostgreSQL): 저장·조회 왕복, EXCLUDE 위반 409·이어지는 세션 허용·다른 멘토 허용·취소 세션 제외, 회차 수, 신청자 겹침(1:1·팀), 목록 정렬·기간·멘토·기수 필터, CHECK 위반, 신청당 세션 하나
- API: 승인(멘토 아님 404, 희망 일시 아님, 성공 → 잔여·보류, 두 번 승인), 반려(사유 누락 422, 성공), 세션 목록·기간 필터·단건(참여자 아님 404)·운영진 목록·단건(다른 기수 404)·403·401
- 전체 717 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 커밋 5개(refactor 포함)를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했다(709 → 710 → 716 → 716 → 717 passed)
- 마이그레이션 18: `upgrade` → `migrate`("No changes detected") → `downgrade -v 18` → `upgrade` 확인, DBML 파서 검증

## 남은 작업
- P11-3: 승인 후 취소(REFUND)·운영진 취소(환불 선택)·변경, 불가 시간 충돌·멘토 변화·수강 종료 연동, 신청 가능 시간에서 세션 제외(`BusySchedule`)
- P12: 승인 커밋 후 Meet Space 생성
