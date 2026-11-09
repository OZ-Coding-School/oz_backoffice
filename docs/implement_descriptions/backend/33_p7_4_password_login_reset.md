# 33. P7-4 수강생·멘토 로그인, 잠금, 비밀번호 재설정

- 상태: PR 진행 중
- 관련 PR: #37
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P7 (P7-4)
- 이전 기록: [32. P7-3 가입 자동 매칭과 승인 알림 메일](32_p7_3_signup_auto_matching.md)

## 배경
P7의 네 번째 PR이다. 가입한 수강생·멘토가 이메일 + 비밀번호로 로그인한다(A2). 비밀번호를 잊으면 이메일 인증코드로 재설정한다(A3). 로그인 실패 잠금과 가입 여부를 드러내지 않는 응답을 적용한다(계획 P7 보안).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `identity/application/verification_codes.py` | `VerificationCodes`: 코드 발급·검증·발송 제한·발송 실패 시 폐기(가입·재설정 공용). 먼저 `refactor:` 커밋으로 가입 서비스에서 옮겼다. IP당 합산 이름을 명시해 가입의 메일·SMS 합산은 그대로 두었다 |
| `identity/application/password_auth.py` | `PasswordLoginService`, `PasswordResetService`, 없는 계정 비교용 해시(`dummy_hash`, 처음 쓸 때 한 번 생성) |
| `identity/infrastructure/login_attempts.py` | Redis 실패 횟수·잠금(이메일 해시 키): 15분 창 5회 → 15분 잠금 |
| `identity/domain/entities.py`, `verification.py` | `User.change_password`, `ChallengeKind.PASSWORD_RESET` |
| `identity/presentation/password_router.py` | `/auth/login`, `/auth/password-reset/code`, `/auth/password-reset` |
| `identity/presentation/router.py` | 토큰 응답 도우미 `respond_with_tokens`를 공개해 운영진·수강생 로그인이 함께 쓴다 |

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/v1/auth/login` | access 토큰(본문) + refresh 쿠키. 실패 401 `invalid_credentials`, 잠금 429 `login_locked` |
| POST | `/api/v1/auth/password-reset/code` | 항상 204. 비밀번호가 있는 회원에게만 실제 발송 |
| POST | `/api/v1/auth/password-reset` | 이메일 + 코드 + 새 비밀번호 → 204 |

- 없는 이메일·Google 전용 계정·틀린 비밀번호는 모두 같은 401이다. 없는 계정도 임의 해시와 비교해 응답 시간 차이를 줄였다.
- 재설정은 새 비밀번호 규칙을 코드 확인보다 먼저 검사한다. 규칙에 맞지 않는 입력으로 코드가 소모되지 않는다.
- 감사 로그: `identity.password.reset`.

## 주요 결정 (사용자 결정, A32)
- **잠금:** 이메일 기준 15분 안에 5회 실패하면 15분 잠금이다. 429 + `Retry-After`로 응답한다. 없는 이메일도 같게 세고, 잠긴 동안에는 맞는 비밀번호도 거부한다.
- **재설정 코드:** 가입 코드와 같은 규칙(6자리·10분·5회·재발송 60초·이메일당 1시간 5회·IP당 1시간 20회)이고, 카운터는 가입과 따로 쓴다.
- **재설정 후 세션:** 기존 세션(refresh 토큰)은 유지한다.
- **재설정 후 잠금:** 재설정하면 로그인 잠금을 푼다.

## 발견한 문제와 해결
- 리팩터링 중 공용 클래스가 IP 카운터 이름을 대상 이름에서 만들고 있었다. 이대로면 가입의 "메일·SMS IP 합산"(A30)이 깨진다. IP 카운터 이름을 인자로 받게 바꿨다.
- 없는 이메일에는 코드를 보내지 않으므로 재발송 간격 응답이 달라질 수 있었다. 없는 이메일도 보내지 않는 코드 기록을 만들어 응답을 같게 했다(테스트로 확인).
- bandit 규칙(S105)이 `ChallengeKind.PASSWORD_RESET` 이름을 비밀번호로 오인했다. 그 줄에만 이유를 적고 예외 처리했다.

## 검증
- 단위:
  - 로그인: 토큰 발급, 이메일 정규화, 세 가지 실패의 같은 응답, Google 전용 계정, 잠금(가입자·없는 이메일), 성공 시 초기화, 승인 대기 로그인·정지 계정 거부, 재해시
  - 재설정: 흐름과 잠금 해제, 없는 이메일·Google 전용 계정 무발송과 같은 동작, 새 비밀번호 검사 순서
- API(PostgreSQL + fakeredis):
  - 로그인 → refresh 쿠키·`/me`(승인 대기)
  - 5회 실패 → 429·`Retry-After`, 재설정 후 새 비밀번호로 로그인
  - 재설정 코드 무노출, 없는 이메일 401
- 커밋 3개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했고 최종 520 passed다.
- 개발 서버: 없는 이메일 로그인 401 확인

## 남은 작업
- P7-5 운영진 승인 관리(대기 목록, 수강생 명단·멘토 계약 선택 승인, 반려 + 알림 메일, 재신청)
