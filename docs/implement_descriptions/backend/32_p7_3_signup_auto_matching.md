# 32. P7-3 가입 자동 매칭과 승인 알림 메일

- 상태: 완료 (2026-11-09 병합)
- 관련 PR: #36
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P7 (P7-3)
- 이전 기록: [31. P7-2 수강생·멘토 가입](31_p7_2_member_signup.md)

## 배경
P7의 세 번째 PR이다. 가입을 완료하면 명단(수강생)이나 계약(멘토)과 이름 + 휴대폰으로 대조해 일치하면 바로 승인한다(A6). 일치하지 않으면 운영진 승인(P7-5)을 기다린다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `academy/application/student_claims.py` | `StudentClaims.claim_in_cohort`: 신청 기수 안의 후보가 정확히 1건일 때 회원에 연결 |
| `educator/application/mentor_onboarding.py` | `MentorOnboarding.link_contracts`: 미연결 멘토 계약(상태 무관)이 있으면 멘토 프로필을 만들고 모두 연결 |
| `educator/…/repositories.py` | `find_unlinked_mentor_contracts`(이름·휴대폰 인덱스 사용), `MentorRepository.add` |
| `identity/application/signup_matching.py` | `SignupMatcher`: 유형별 매칭 규칙, 수강생 STUDENT 역할(기수 범위) 부여 |
| `identity/application/signup.py` | 가입 완료 트랜잭션에서 매칭 → MATCHED면 회원·신청 승인. 커밋 후 승인 알림 메일을 워커로 보낸다(`approval_mail`, 이름은 HTML 이스케이프). 감사 로그에 매칭 결과·상태 |
| `identity/domain/signup.py` | `record_match` |
| `workers/tasks/notifications.py` | `notifications.send_mail`: 최대 3회 시도(5초·30초 간격), 실패해도 처리는 유지. `TaskiqMailDispatcher` |
| `main.py` | `app.state.signup_matcher`(academy·educator·access 공개 서비스 조립), `app.state.mail_dispatcher` |
| `docker-compose.yml` | 워커·스케줄러 명령에 `app.workers.tasks.notifications` |
| `tests/conftest.py` | 테스트 앱은 메모리 디스패처를 써 실제 큐로 보내지 않는다 |

- 다른 컨텍스트 서비스(`StudentClaims`, `MentorOnboarding`, `RoleAssignmentService.grant`)는 자체 트랜잭션을 열지 않는다. 가입 서비스의 트랜잭션 안에서 실행되므로 매칭 중 오류가 나면 회원 생성까지 함께 되돌린다.

## 주요 결정 (사용자 결정, A31)
- **수강생 매칭:**
  - 대상은 수강 중(ENROLLED) 명단만이다.
  - 신청한 기수 안에서만 찾는다. 사용자 지적대로 동시 수강은 없으므로 같은 기수의 후보가 정확히 1건이면 MATCHED다. 0건이면 NO_MATCH, 2건 이상(데이터 중복)이면 AMBIGUOUS다.
  - 다른 기수에 명단이 있으면 승인 대기가 된다.
- **멘토 매칭:** 계약 상태와 무관하게 매칭하고, 일치하는 미연결 멘토 계약을 모두 연결한다.
- **MENTOR 역할:** 계획에는 "부여"로 적혀 있었다. A17(멘토 역할은 배정에서만)과 기수 범위 문제가 있어 가입 때는 주지 않는다. 멘토 배정(P8)에서 준다.
- **알림 메일:** 자동 승인도 커밋 후 워커로 보낸다.

## 발견한 문제와 해결
- 승인 메일 HTML에 회원 이름을 넣는다. 이름이 이스케이프되지 않으면 HTML이 주입될 수 있어 `html.escape`로 처리했다(테스트로 확인).
- 공용 테스트 앱이 실제 `TaskiqMailDispatcher`를 쓰면 개발 Redis 큐로 작업이 들어갈 수 있다. conftest에서 메모리 디스패처로 바꿨다.

## 검증
- 단위:
  - 가입 서비스: 매칭 결과별 상태, 역할, 알림 메일, 감사 로그(NO_MATCH·AMBIGUOUS는 대기·메일 없음, MATCHED 수강생은 역할 + 메일, MATCHED 멘토는 역할 없음 + 메일)
  - 이름 이스케이프
  - 알림 작업 재시도(0·2·5회 실패)
- 통합(PostgreSQL):
  - 명단 연결: 다른 기수·수강 중 아님·원천 삭제 제외, 0건·2건은 연결하지 않음
  - 멘토 계약 연결: DRAFT·ENDED 연결, 강사 계약·이미 연결된 계약 제외, 프로필 닉네임
- API(PostgreSQL + fakeredis): 신청 기수에 명단이 있으면 APPROVED가 되고, 명단 연결·STUDENT 역할·MATCHED 기록·승인 메일 디스패치를 확인했다. 다른 기수에만 명단이 있으면 PENDING·NO_MATCH다.
- 커밋 3개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했고 최종 503 passed다.
- 개발 환경: 재시작한 워커가 `app.workers.tasks.notifications`를 불러온다.
- GitHub Actions (PR #36, run 42628974898): backend 잡 통과, 503 passed

## 남은 작업
- P7-4 로그인·잠금·비밀번호 재설정
- P7-5 운영진 승인 관리(대기 목록, 수강생 명단·멘토 계약 선택 승인, 반려 + 알림 메일, 재신청)
- 운영: 가입 전에 역할 시드(`seed-roles`)가 되어 있어야 수강생 자동 승인이 된다(없으면 409 `role_not_seeded`)
