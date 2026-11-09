# 31. P7-2 수강생·멘토 가입 (인증코드·레이트 리밋·가입 신청)

- 상태: 완료 (2026-11-09 병합)
- 관련 PR: #35
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P7 (P7-2)
- 이전 기록: [30. P7-1 메일·SMS 발송 기반과 Gmail 드라이버](30_p7_1_notification_senders.md)

## 배경
P7의 두 번째 PR이다. 수강생·멘토가 gmail 이메일 인증과 휴대폰 SMS 인증을 거쳐 가입하는 흐름을 만든다(A2·A3). 가입하면 회원은 승인 대기(PENDING)가 된다. 자동 매칭(P7-3)과 운영진 승인(P7-5)은 이 가입 신청을 이어서 처리한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `identity/domain/signup.py`, `enums.py` | `MemberSignup`(유형별 입력 규칙, 승인·반려), `MemberSignupType`·`MemberSignupStatus`·`SignupMatchResult` |
| `identity/domain/credentials.py` | 비밀번호 규칙 |
| `identity/domain/verification.py` | 인증코드(`CodeChallenge`)·가입 세션(`SignupSession`) 값과 저장소 Protocol, 코드 규칙 상수 |
| `identity/infrastructure/models.py`, `migrations/models/10_…` | `member_signups` 테이블 + raw SQL(기본값, enum·DBML check, 회원당 대기 신청 부분 유니크) |
| `identity/infrastructure/verification_store.py` | 인증코드·가입 세션 Redis 저장소. 키에는 이메일·휴대폰·토큰 대신 SHA-256 해시를 넣는다 |
| `identity/infrastructure/passwords.py` | argon2id 해시(스레드에서 계산) |
| `identity/application/signup.py` | `SignupService`: 이메일 코드 발송·확인 → 가입 토큰 → SMS 코드 발송·확인 → 가입 완료 |
| `identity/presentation/signup_router.py` | `/api/v1/auth/signup/*` API |
| `core/rate_limit.py`, `core/client_ip.py` | Redis 고정 창 레이트 리밋, 신뢰 프록시 기반 클라이언트 IP |
| `shared/errors.py`, `core/errors.py` | `TooManyRequestsError` → 429 + `Retry-After` |
| `academy/application/catalog.py` | `is_signup_cohort`(가입 기수 검증) |
| `core/config.py`, `.env.example` | `TRUSTED_PROXIES` |

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/v1/auth/signup/cohorts` | 가입 때 고를 기수(활성 과정의 PLANNED·ONGOING) |
| POST | `/api/v1/auth/signup/email-code` | gmail로 인증코드 발송 (204) |
| POST | `/api/v1/auth/signup/email-code/verify` | 코드 확인 → `signup_token`(30분) |
| POST | `/api/v1/auth/signup/phone-code` | 가입 토큰 + 휴대폰 → SMS 인증코드 (204) |
| POST | `/api/v1/auth/signup/phone-code/verify` | SMS 코드 확인 (204) |
| POST | `/api/v1/auth/signup` | 가입 완료 → 회원 PENDING + 가입 신청 (201, 토큰 없음) |

- 코드는 HMAC-SHA256(키: JWT 시크릿)으로만 저장하고 `hmac.compare_digest`로 비교한다. 5번째 실패나 만료면 코드를 지운다.
- 발송에 실패하면 방금 저장한 코드를 지우고 503(`mail_delivery_failed` 등)으로 알린다.
- 가입 완료 때 트랜잭션 안에서 이메일·휴대폰 중복을 다시 확인한다. 인증 이후 다른 요청이 먼저 가입했을 수 있어서다. 동시 경합은 DB 유니크와 409 안전망이 막는다.
- 가입 감사 로그: `identity.member_signup.create`(행위자 = 가입한 회원).

## 주요 결정 (사용자 결정, A30·B14)
- **비밀번호:** 8~64자, 영문·숫자·특수문자를 각각 1개 이상 쓴다. 해시는 argon2-cffi(argon2id)로 한다.
- **중복 이메일:** 이미 가입된 이메일로 코드를 요청하면 409로 바로 알린다.
- **레이트 리밋:** 대상(이메일·휴대폰)당 1시간 5회, IP당 1시간 20회(메일·SMS 합산)다. IP는 `TRUSTED_PROXIES`에 든 프록시에서 온 요청만 `X-Forwarded-For`로 판단한다.
- **가입 완료 후:** 토큰을 주지 않고 다시 로그인하게 한다(로그인 API는 P7-4).
- **가입 신청:** `member_signups`에 운영진 신청과 같은 구조로 둔다. 회원의 승인 상태는 `users.approval_status`에 함께 둔다.
- **가입 입력:** 수강생은 기수가 필수다. 기수 목록은 인증 없이 공개하고 활성 과정의 PLANNED·ONGOING만 보여 준다. 멘토는 닉네임·표시 이름을 선택 입력한다.
- **이후 PR에서 적용할 결정:** 반려 후 재신청을 허용한다. 승인·반려하면 커밋 후 워커가 알림 메일을 보낸다(재시도 3회, P7-5).
- **되돌린 검토:** 사용자가 "승인 전에는 users 행을 만들지 않는" 구조를 제안했다. 운영진 가입까지 바꾸는 범위를 검토하던 중 "너무 복잡해진다"며 되돌렸다. 기존 A6(대기 중 로그인·상태 화면)과 A11(운영진 대기 중 신청 수정)은 그대로다.

## 발견한 문제와 해결
- 단위 테스트에서 발견: "재발송 60초" 때문에 거부된 요청도 시간당 발송 횟수에 들어가고 있었다. 재발송 간격을 레이트 리밋보다 먼저 검사하도록 순서를 바꿨다. 실제로 발송한 요청만 센다.

## 검증
- 단위:
  - 가입 신청 규칙(유형별 입력, 처리 전이), 비밀번호 경계(8·64자, 구성)
  - 클라이언트 IP 판정(위조 헤더 무시, 프록시 체인)
  - 레이트 리밋 창, Redis 저장소(키에 개인정보 없음), argon2
  - 가입 서비스:
    - 전체 흐름, 멘토 입력
    - gmail 외 거부, 가입된 이메일·휴대폰 거부
    - 시도 5회와 만료, 재발송 간격과 대상·IP 제한
    - 발송 실패 시 코드 폐기, 가입 완료 검증
- 통합(PostgreSQL): `member_signups` 저장 왕복, 회원당 대기 신청 하나, check 제약 5종, DB 기본값
- API(PostgreSQL + fakeredis + 메모리 발송):
  - 가입 전체 흐름(argon2 해시 저장, 토큰 미발급), 가입 후 같은 이메일 409
  - 공개 기수 목록(종료 기수 제외), gmail 외 422
  - 재발송 429 + `Retry-After`, 신뢰 프록시 없을 때 `X-Forwarded-For` 무시(IP당 20회)
  - 중복 휴대폰 409, 휴대폰 인증 전 가입 422
- 개발 서버: 공개 기수 목록 15개(실데이터), 이메일 코드 요청 204와 console 출력 확인
- 커밋 5개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했고 최종 489 passed다.
- GitHub Actions (PR #35, run 42626543436): backend 잡 통과, 489 passed

## 남은 작업
- P7-3 자동 매칭(가입 완료에 붙여 일치하면 바로 승인)
- P7-4 로그인·잠금·비밀번호 재설정, P7-5 승인 관리(재신청, 알림 메일)
- 운영 배포 때 `TRUSTED_PROXIES`에 nginx 주소 설정
