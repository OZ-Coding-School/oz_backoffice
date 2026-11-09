# 30. P7-1 메일·SMS 발송 기반과 Gmail 드라이버

- 상태: PR 진행 중
- 관련 PR: (작성 예정)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P7 (P7-1)
- 이전 기록: [29. P6-4 계약 수동 연결과 멘토 프로필 API](29_p6_4_contract_link_mentor_profile.md)

## 배경
P7(수강생·멘토 가입)의 첫 PR이다. 가입 인증코드(이메일·SMS)와 비밀번호 재설정 코드를 보낼 발송 기반을 만든다. SMS 업체는 아직 정하지 않았다(A4). 메일은 회사 Workspace Gmail API로 지금 구현한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `integrations/notifications/mail.py` | `MailMessage`, `MailSender` Protocol, `ConsoleMailSender`(받는 주소를 가려 로그 출력), `GmailSender`(서비스 계정 + 도메인 전체 위임, `gmail.send`, 텍스트 + HTML), `DisabledMailSender`(503 `mail_not_configured`), 실패는 `MailDeliveryError`(503) |
| `integrations/notifications/sms.py` | `SmsMessage`, `SmsSender` Protocol, `ConsoleSmsSender`(번호를 가려 로그 출력), `DisabledSmsSender`(503 `sms_not_configured`) |
| `core/notifications.py` | 설정으로 드라이버 선택. 운영의 console이나 Gmail 설정 누락은 발송만 거부한다(앱은 기동) |
| `core/config.py`, `.env.example` | `MAIL_DRIVER`(console/gmail), `SMS_DRIVER`(console), `MAIL_SENDER_NAME`, `GMAIL_SENDER`, `GOOGLE_SERVICE_ACCOUNT_JSON` |
| `core/dependencies.py`, `main.py` | `app.state.mail_sender`·`sms_sender`, `get_mail_sender`·`get_sms_sender` |
| `cli.py` | `send-test-mail <받는주소>`: 현재 드라이버로 확인 메일 발송. CLI도 로그 설정을 적용해 console 출력이 보인다 |
| `tests/fakes/notifications.py` | 메모리 드라이버(P7-2부터 발송 내용 검증용) |

- Gmail 호출은 동기 라이브러리라 `asyncio.to_thread`로 실행한다. httplib2 기반 서비스 객체는 스레드 간에 공유하지 않으므로 발송마다 만든다. discovery 문서는 라이브러리에 포함된 것을 쓴다(네트워크 조회 없음).
- 발송 실패 로그에는 받는 주소를 남기지 않고 예외 종류만 남긴다.

## 주요 결정 (사용자 결정)
- **A29 P7 발송:**
  - PR은 5개로 나눈다.
  - SMS는 console 드라이버로 개발한다.
  - 메일은 Gmail API로 지금 구현하고, 발신은 기존 운영 계정으로 한다.
  - 인증코드는 API 요청 안에서 바로 발송한다.
  - 메일은 텍스트 + HTML이고, 발신자 표시 이름은 '오즈코딩스쿨'이다.
  - SMS 문구는 짧은 한 건으로 한다.
  - 운영에서 console 드라이버이면 발송만 503으로 거부한다.
  - 확인용 CLI를 둔다.
- **B13 Google API:**
  - google-api-python-client + google-auth를 쓴다.
  - 키는 환경변수에 JSON 원문으로 넣는다.
  - 타입은 google-api-python-client-stubs로 검사한다.
  - 타입 주석이 없는 google-auth 생성 함수 한 곳만 `type: ignore[no-untyped-call]`로 둔다.

## 발견한 문제와 해결
- **cryptography `Illegal instruction`:**
  - google-api-python-client가 끌어오는 cryptography 50.0.2를 로컬 Docker(Apple M4, aarch64)에서 import하면 프로세스가 죽었다. 버전별로 재보니 47 이상이 죽고 46.0.3 이하는 정상이었다.
  - 사용자 요청으로 46.x 고정 전에 보안 이슈를 조사했다. 46.0.3 이후 고쳐진 취약점이 5건 있었다: CVE-2026-26007, CVE-2026-34073, CVE-2026-39892, GHSA-537c-gmf6-5ccf, CVE-2026-69249. 그래서 고정은 하지 않기로 했다.
  - 원인은 이전 Docker Desktop의 VM이 SVE2·SME 기능을 잘못 알려 OpenSSL이 실행할 수 없는 명령어 경로를 고른 것이었다. `OPENSSL_armcap=0`으로 우회되는 것을 확인했다.
  - 사용자가 Docker Desktop을 업데이트(엔진 29.9.3)한 뒤 우회 없이 최신 버전이 정상 동작했다. 버전 고정·우회 설정 없이 최신을 쓴다.
- **mypy:**
  - googleapiclient 타입 정보가 없었다. 사용자 결정으로 서드파티 스텁을 추가했다.
  - google-auth `from_service_account_info`는 스텁 대상이 아니어서 그 호출 한 곳만 예외를 두었다.

## Gmail 발송 설정 방법
1. **Google Cloud:** 프로젝트에서 Gmail API를 사용 설정한다.
2. **서비스 계정:** 프로젝트 역할은 부여하지 않는다. 세부정보의 **고유 ID(숫자)**를 적어 둔다.
3. **키:**
   - 키 탭 → 새 키 → JSON으로 만든다.
   - 조직 정책 `iam.disableServiceAccountKeyCreation`이 막으면 조직 관리자가 예외를 허용해야 한다.
   - 키 파일은 저장소에 넣지 않는다.
4. **Workspace 관리 콘솔:**
   - 보안 → 액세스 및 데이터 관리 → API 관리 → 도메인 전체 위임 → 새로 추가로 들어간다.
   - 클라이언트 ID에는 고유 ID를, 범위에는 `https://www.googleapis.com/auth/gmail.send`를 넣는다.
   - 반영까지 몇 분에서 최대 24시간이 걸린다.
5. **발신 계정:** Gmail 라이선스가 있는 실제 사용자여야 한다. 그룹·별칭 주소는 안 된다.
6. **`apps/backend/.env`:**
   - `MAIL_DRIVER=gmail`, `GMAIL_SENDER=<계정>`을 넣는다.
   - `GOOGLE_SERVICE_ACCOUNT_JSON='<한 줄 JSON>'`을 넣는다. 한 줄 변환 명령:
     ```bash
     python3 -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1]))))" key.json
     ```
7. **확인:**
   - `docker compose up -d`(값 반영) → `docker compose exec api python -m app.cli send-test-mail <받는주소>`
   - 오류: `unauthorized_client`는 위임 미반영이나 ID·범위 불일치다. `failedPrecondition`은 메일함이 없는 계정이다. `invalid_grant`는 키 폐기나 시각 문제다.

## 검증
- 단위:
  - MIME: 한글 제목·표시 이름 인코딩, 텍스트/HTML 대체 본문, 텍스트만 있는 메일
  - Gmail 드라이버(가짜 서비스): 위임 대상이 발신 계정이고 raw MIME으로 보내는지, 실패 시 503과 로그에 받는 주소가 남지 않는지
  - console 드라이버: 주소·번호 마스킹
  - 서비스 계정 JSON 파싱
  - 드라이버 선택: 운영 console → 503, Gmail 설정 누락 → 503
- `send-test-mail` console 출력 확인(받는 주소 마스킹)
- 커밋 2개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했고 최종 440 passed다.
- 실제 Gmail 발송은 사용자 설정 후 `send-test-mail`로 확인한다(아직 하지 않음).

## 남은 작업
- 사용자: 서비스 계정·도메인 위임 설정 후 실제 발송 확인
- SMS 업체 결정 후 업체 어댑터
- P7-2 인증코드·레이트 리밋·가입
