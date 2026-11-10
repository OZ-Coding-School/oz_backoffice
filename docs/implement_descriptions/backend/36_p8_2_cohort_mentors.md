# 36. P8-2 기수 멘토 배정·멘토 활성화·팀리드 권한

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P8 (P8-2), §2.3 권한표
- 이전 기록: [35. P8-1 기수 멘토링 설정·금지 시간대·추가 휴일](35_p8_1_mentoring_settings.md)

## 배경
P8의 두 번째 PR이다. 운영진이 기수에 멘토를 배정하고(유형·기간·정산 조건) 멘토 본인이 자기 배정을 본다. 배정은 이후 멘토 일정(P9)·팀(P10)·신청(P11)·정산(P14)의 기준이 된다. 진행 중에 요구사항이 바뀌었다. 계약과 배정을 따로 관리하게 됐고(M15 폐기), 멘토 활성 여부(A28에서 미룸)를 정했으며, 멘토 관리 권한을 새로 나누면서 팀리드 역할이 생겼다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/assignment.py`, `enums.py` | `CohortMentor`: 기간·단가 기준·금액 검증, 시작일 기수 기간 검사, 수정 항목 제한, 비활성(사유·시각)·재활성, 만료 판단 |
| `mentoring/infrastructure/models/assignment.py`, `migrations/models/12_…` | `cohort_mentors`: 종료일 NULL 허용, 비활성 시각·사유, check 4종, 활성 배정 부분 유니크 `uid_cohort_mentors_active` |
| `mentoring/infrastructure/repositories.py` | 배정 리포지토리. 부분 유니크 위반을 409 `assignment_already_exists`로 바꾼다 |
| `mentoring/application/assignment_service.py` | `CohortMentorService`: 등록·수정·비활성화·재활성화, 기수별·본인 목록, 만료 처리 |
| `mentoring/application/mentor_activation.py` | `MentorActivationService`: 멘토 비활성화(미리보기·확인), 재활성화와 복구 후보, 일괄 재활성화(가능한 것만) |
| `mentoring/presentation/assignment_router.py` | API (아래 표) |
| `educator/application/mentor_queries.py` | 멘토링용 공개 서비스: 조회·묶음 조회·행 잠금·활성 변경 (`app.state.mentor_queries`) |
| `educator/domain/profiles.py` | `Mentor.activate/deactivate/display_name` |
| `academy/application/catalog.py` | `get_cohort`, `cohort_labels`(과정명·기수 번호) |
| `access/domain/catalog.py`, `application/role_admin.py` | `mentor.manage`·`staff.assign` 권한, TEAM_LEAD 역할, 직접 관리 역할에 TEAM_LEAD 추가 |
| `workers/tasks/mentoring.py` | `mentoring.assignments.expire` 매일 00:00 KST (compose 워커·스케줄러에 등록) |

| 메서드 | 경로 | 권한 |
| --- | --- | --- |
| GET / POST | `/api/v1/admin/cohorts/{cohort_id}/mentor-assignments` | `mentoring.assignment.manage` 기수 범위. 목록은 페이징 없음, `include_inactive` |
| PATCH / DELETE | `/api/v1/admin/cohorts/{cohort_id}/mentor-assignments/{id}` | 같음. DELETE = 비활성화(MANUAL) |
| POST | `/api/v1/admin/cohorts/{cohort_id}/mentor-assignments/{id}/reactivate` | 같음 |
| POST | `/api/v1/admin/mentors/{id}/deactivate` | `mentor.manage`. `confirm=false`면 미리보기(안내 문구 + 함께 꺼질 배정), `true`면 실행 |
| POST | `/api/v1/admin/mentors/{id}/activate` | `mentor.manage`. 응답에 복구 후보 배정 |
| POST | `/api/v1/admin/mentors/{id}/mentor-assignments/reactivate` | `mentor.manage`. 가능한 것만 켜고 실패는 사유와 함께 |
| GET | `/api/v1/me/mentor-assignments?include_inactive=` | 멘토 본인. 과정명·기수 번호·정산 조건 포함 |

기존 `/api/v1/admin/mentors`(목록·프로필 대리 수정·사진)는 `contract.manage`에서 `mentor.manage`로 바꿨다. `/admin/cohorts|bootcamps/{id}/staffs`는 `role.assign`에서 `staff.assign`으로 바꿨다.

## 주요 결정 (사용자 결정, A35·A36)
- **배정 판단:**
  - 배정 여부는 `cohort_mentors`로만 판단하고 MENTOR 역할은 쓰지 않는다.
  - 활성 배정은 (멘토, 기수, 유형)당 하나다. 기존 M12의 기간 겹침 EXCLUDE는 부분 유니크로 바꿨다.
- **계약과 분리:** 계약 연동 방식을 묻던 중 사용자가 요구사항을 바꿨다. 계약과 기수 배정은 별개이고, 운영진이 계약서와 무관하게 배정을 등록·수정·삭제·조회한다(M15 폐기).
- **기간:**
  - 시작일은 기수 기간 안이어야 한다.
  - 종료일은 없어도 되고, 기수 기간 밖이어도 된다.
  - 종료일이 만료일이다. 매일 00:00 KST에 종료일이 지난 배정을 비활성화한다(종료일 당일까지 활성).
- **삭제와 수정:**
  - 삭제는 비활성화다.
  - 기간·정산 조건은 언제든 고친다. 멘토·기수·유형은 바꾸지 않는다.
  - 비활성 배정은 다음 조건을 모두 만족하면 다시 켠다: 종료일이 없거나 오늘 이후, 같은 키의 활성 배정 없음, 멘토 활성.
  - 질문 중 "배정"이라는 말이 모호하다는 지적이 있었다. 이후 질문은 "기수에 멘토를 배정한 내용(cohort_mentors 한 행)"으로 풀어 썼다.
- **멘토 비활성화:**
  - 멘토를 끄면 그 멘토의 배정도 모두 꺼지고, 이를 안내 문구로 보여 준다. 비활성 멘토는 새 배정을 받지 못한다.
  - 미리보기 후 확인(confirm) 방식이다.
  - 멘토를 다시 켜면 추가 팝업으로 배정 복구를 안내한다. 복구 후보는 비활성 사유로 구분한다(MENTOR_DEACTIVATED).
  - 일괄 재활성화는 가능한 것만 켠다.
- **본인 조회:** 정산 조건까지 보여 준다.
- **권한(A36):**
  - 멘토 관리 전체(목록·프로필·활성화)를 새 권한 `mentor.manage`로 옮겼다. SUPER_ADMIN·TEAM_LEAD·매니저에 주고, 범위가 하나라도 있으면 허용한다.
  - **TEAM_LEAD(팀리드)** 역할을 새로 만들었다. 권한은 매니저 권한 + 멘토 관리 + 인사권한이다.
  - 인사권한에 기존 `role.assign`을 그대로 주면 팀리드가 SUPER_ADMIN을 부여할 수 있었다. 이를 알린 뒤 사용자가 "담당자 배정만"으로 정했고, `staff.assign`으로 분리했다.
  - 팀리드는 회원 역할 API로 GLOBAL 범위에서 부여한다(부여자는 SUPER_ADMIN).
- **목록:** 기수별 배정 목록은 페이지네이션 없이 준다(하네스 "목록은 페이지네이션" 규칙의 예외, 사용자 결정).

## 구현 세부
- 배정 생성·재활성화·일괄 재활성화와 멘토 비활성화는 모두 멘토 행을 `SELECT … FOR UPDATE`로 잠근다. 멘토를 끄는 동안 새 배정이 생기지 않게 하기 위해서다. 그래도 동시 요청이 겹치면 부분 유니크가 막고, 리포지토리가 409로 바꾼다.
- 복구 후보에서 같은 (기수, 유형)의 비활성 배정이 여럿이면 가장 최근에 꺼진 것만 보여 준다(활성 배정은 키당 하나라서).
- 목록 응답의 멘토 이름은 멘토·회원을 한 번씩 묶어 조회한다. 쿼리 수는 배정 수와 무관하게 일정하다.
- 감사 로그 액션은 두 가지다.
  - 배정: `mentoring.assignment.create|update|deactivate|reactivate|expire`(만료는 actor 없음)
  - 멘토: `educator.mentor.activate|deactivate`(함께 끈 배정 수 포함)

## 발견한 문제와 해결
- 기존 통합 테스트는 부분 유니크 위반을 `IntegrityError`로 기대했다. 리포지토리가 409로 바꾸게 되면서 `ConflictError(assignment_already_exists)`로 고쳤다.
- 이전 세션이 결정 질문 중에 중단됐다. 질문 세 가지(일괄 재활성화 실패 처리, 멘토 비활성화 범위, 목록 페이징)를 다시 물어 확정했다.

## 검증
- 단위:
  - 배정 서비스: 생성 규칙(중복·시작일·종료일 기수 밖), 없는/비활성 멘토, 수정·비활성·재활성, 만료 멱등
  - 멘토 활성화: 미리보기·확인, 복구 후보, 일괄 재활성화 부분 성공과 실패 사유 5종
  - 권한표: 팀리드 = 매니저 + `staff.assign`. 작업 스케줄 00:00 KST
- 통합(PostgreSQL): 부분 유니크(409), 다른 유형 허용, 비활성 후 재배정, 종료일 NULL, 만료 목록, check 제약
- API:
  - 배정: CRUD, 중복 409, 시작일 밖·MONTHLY 422, 종료일 비우기
  - 멘토 활성화: 비활성화 미리보기·실행, 비활성 멘토 배정·재활성 422, 재활성화 후보, 일괄 재활성화
  - 본인 조회, 멘토 프로필 없음 404
  - 권한: 매니저 담당 기수 201·다른 기수 403, 조교 403, `mentor.manage` 매니저 200·조교 403, 비로그인 401, 팀리드 담당자 API 200·역할 부여 403·운영진 가입 승인 403
- 전체 595 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 코드 커밋 4개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했다(581 → 582 → 590 → 595 passed)
- 워커·스케줄러 재기동 후 `app.workers.tasks.mentoring` 등록 확인. 개발 DB에 `seed-roles`로 TEAM_LEAD·새 권한 반영

## 배포 시 주의
- 역할·권한 정의가 바뀌었으므로 배포 후 `python -m app.cli seed-roles`를 실행한다(판정은 코드 기준이라 시드 전에도 동작한다, A16).
- 워커·스케줄러 실행 명령에 `app.workers.tasks.mentoring`을 추가해야 한다. 추적하지 않는 `docker-compose.prod.yml`에는 반영하지 않았다.

## 남은 작업
- 배정 적용: P9(일정 열기·금지 시간대), P10(팀 담당 멘토는 활성 배정), P11(신청), P14(정산 단가 스냅샷)
- 운영 compose(`docker-compose.prod.yml`)의 워커 모듈 목록 갱신
