# 34. P7-5 수강생·멘토 가입 승인 관리와 재신청

- 상태: PR 진행 중
- 관련 PR: (작성 예정)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P7 (P7-5)
- 이전 기록: [33. P7-4 로그인·잠금·비밀번호 재설정](33_p7_4_password_login_reset.md)

## 배경
P7의 마지막 PR이다. 자동 매칭(P7-3)에서 승인되지 않은 수강생·멘토를 운영진이 담당 범위 안에서 승인하거나 반려한다. 반려된 회원은 로그인해 사유를 확인하고 다시 신청할 수 있다(A6·A30).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `access/application/permissions.py` | `PermissionChecker.scope_of`: 권한 코드별 범위(전체 / 과정·기수 ID) — 목록 필터용 |
| `academy/application/student_claims.py` | `cohort_of_claimable`·`claim_selected`: 운영진이 고른 명단 확인·연결(미가입·원천 존재, 수강 상태 무관) |
| `educator/application/mentor_onboarding.py` | `approve`: 고른 계약(유형 MENTOR·미연결, 0건 이상) 연결 + 멘토 프로필. 자동 매칭과 프로필 생성 코드를 공유 |
| `identity/domain` | `User.resubmit`(REJECTED → PENDING), `SignupVisibility`·`PendingSignupFilter`, 리포지토리 `get_pending_by_user`·`list_pending` |
| `identity/infrastructure/repositories.py` | 대기 목록 범위 조건(신청 기수 / 기수의 과정 / 멘토 전부), 오래된 순 |
| `identity/application/signup_review.py` | `SignupReviewService`(목록·수강생 승인·멘토 승인·반려), `MemberSignupSelfService`(최근 신청·재신청) |
| `identity/application/signup_mails.py` | 승인·반려 메일(이름·사유 HTML 이스케이프) |
| `identity/application/signup.py` | `settle_auto_match`: 가입 완료와 재신청이 함께 쓰는 자동 매칭 정산 |
| `identity/presentation/approval_router.py`, `main.py` | API, `app.state.student_claims`·`mentor_onboarding` |

| 메서드 | 경로 | 권한 |
| --- | --- | --- |
| GET | `/api/v1/admin/approvals` | `user.approve` (수강생은 담당 기수만, 멘토는 `contract.manage`가 있을 때) |
| POST | `/api/v1/admin/approvals/{user_id}/approve` | 수강생: `student_id`(신청 기수·명단 기수 모두 담당), 멘토: `contract_ids`(0건 이상, `contract.manage`) |
| POST | `/api/v1/admin/approvals/{user_id}/reject` | 사유 필수(300자). 수강생은 신청 기수 담당, 멘토는 `contract.manage` |
| GET | `/api/v1/me/member-signup` | 로그인 회원 — 최근 신청(상태·반려 사유) |
| POST | `/api/v1/me/member-signup` | 반려된 회원 — 재신청(자동 매칭 다시) |

- 감사 로그: `identity.member_signup.approve`(연결한 명단·기수 또는 멘토·계약), `.reject`(사유), `.resubmit`(매칭 결과).
- 승인·반려는 커밋 후 알림 메일을 워커로 보낸다(A30).

## 주요 결정 (사용자 결정, A33)
- **수강생 승인:**
  - 다른 기수 명단도 고를 수 있다. 승인자 담당 범위 안의 미가입·원천 존재 명단이고 수강 상태는 묻지 않는다.
  - 신청 기수와 고른 명단의 기수 모두 승인자 범위여야 한다. 역할은 고른 명단의 기수 범위로 준다.
- **멘토 승인:** 계약 없이 승인할 수 있다(0건 이상).
- **재신청:** 반려된 회원이 로그인해 새로 신청하면 자동 매칭을 다시 한다.

## 발견한 문제와 해결
- 목록을 페이지로 가져온 뒤 권한으로 거르면 한 페이지가 비게 된다. 그래서 `scope_of`로 범위를 먼저 구해 DB 조회 조건으로 넣었다. 과정 범위는 신청 기수의 과정으로 조인한다.
- 가입 완료와 재신청이 같은 자동 매칭·승인·메일 처리를 쓴다. 이를 `settle_auto_match`로 모았다.

## 검증
- 단위:
  - `scope_of`(없음, 기수·과정 범위, 역할별 권한 차이, 전체)
  - 회원 재신청 전이, 가입 서비스 기존 시나리오 유지
- 통합(PostgreSQL):
  - 대기 목록 범위 필터(없음·기수·과정·멘토·전체·유형·기수 필터), 대기 신청 조회
  - 고른 명단 규칙(수료생 연결, 이미 연결·원천 삭제 거부, 없는 명단), 고른 계약 규칙(강사 계약·없는 계약 거부)
- API(PostgreSQL):
  - 최고 관리자가 다른 기수 명단으로 승인: 명단 연결, 그 기수 STUDENT 역할, 승인 메일, 목록에서 빠짐
  - 조교: 자기 기수 신청만 보이고, 다른 기수 반려·멘토 승인·범위 밖 명단 선택은 403
  - 계약 없는 멘토 승인으로 프로필 생성
  - 반려(사유 이스케이프 메일) → 내 신청 조회 → 재신청 PENDING·NO_MATCH → 반려 아닌 상태 재신청 거부
  - 권한 401·403
- 커밋 4개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했고 최종 531 passed다.

## 남은 작업
- P8 기수 멘토링 설정·멘토 배정(MENTOR 역할 부여, 멘토 활성 여부)
- 실제 Gmail 발송 확인(사용자 설정 후 `send-test-mail`), SMS 업체 결정 후 어댑터
