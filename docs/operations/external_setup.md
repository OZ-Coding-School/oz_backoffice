# 외부 준비물 설정 가이드

개발에 필요한 외부 서비스 설정을 모았다. 운영 서버 배포 설정은 [`production_notes.md`](production_notes.md)에 따로 정리한다.
값(키·시크릿)은 이 문서나 저장소에 적지 않는다. `apps/backend/.env`(로컬)나 운영 비밀 저장소에만 넣는다.

| # | 준비물 | 필요한 단계 | 담당 | 상태 (2026-11-11) |
| --- | --- | --- | --- | --- |
| 1 | Google 서비스 계정 + 도메인 전체 위임(DWD) — Gmail 발송 | P7 (구현 완료, 실발송 미확인) | GCP 관리자 + Workspace 관리자 | **진행 중**: 키는 유효, 위임 단계에서 `unauthorized_client` |
| 2 | DWD에 Meet·Drive 범위 추가 | P12, P13 | Workspace 관리자 | 미착수 |
| 3 | Google Cloud API 사용 설정 + Pub/Sub 토픽·구독 | P12 | GCP 관리자 | 미착수 |
| 4 | SMS 발송 업체 계약·발신번호 등록 | P7 어댑터(별도 PR) | 사용자 | 업체 미정 (현재 console 드라이버) |
| 5 | Google OAuth 클라이언트 (운영진 로그인) | P2 (구현 완료) | GCP 관리자 | 로컬 등록 완료, 운영 URI는 배포 때 |
| 6 | Airtable 토큰 | P5 (구현 완료) | 사용자 | 완료 |
| 7 | AWS S3 운영 버킷·IAM | 운영 배포 | AWS 관리자 | 배포 때 ([운영 참고](production_notes.md#3-aws-s3)) |

---

## 1. Google 서비스 계정 + 도메인 전체 위임 (Gmail 발송)

백엔드는 서비스 계정이 회사 계정(`GMAIL_SENDER`)을 대신해 Gmail API로 메일을 보낸다(decisions A8·A29·B13). 범위는 `https://www.googleapis.com/auth/gmail.send` 하나다.

### 1-1. 서비스 계정과 키 (GCP 콘솔)
1. [Google Cloud Console](https://console.cloud.google.com/)에서 회사 Workspace 조직에 속한 프로젝트를 고른다(없으면 만든다).
2. **API 및 서비스 → 라이브러리**에서 **Gmail API**를 사용 설정한다.
3. **IAM 및 관리자 → 서비스 계정 → 서비스 계정 만들기**. 이름 예: `oz-backoffice`. 프로젝트 역할은 주지 않아도 된다(Gmail 발송에는 IAM 역할이 필요 없다).
4. 만든 서비스 계정 → **세부정보** 탭에서 **고유 ID(숫자 21자리, OAuth 2 클라이언트 ID)** 를 복사해 둔다. 1-2에서 쓴다.
5. **키 → 키 추가 → 새 키 만들기 → JSON**. 내려받은 파일은 저장소 밖에 보관한다.
   - 조직 정책 `iam.disableServiceAccountKeyCreation`이 켜져 있으면 키를 만들 수 없다. 조직 관리자가 이 프로젝트만 예외로 둬야 한다.
6. `.env`에는 JSON을 한 줄로 바꿔 작은따옴표로 감싸 넣는다.
   ```bash
   python3 -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1]))))" key.json
   # → GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
   ```

### 1-2. 도메인 전체 위임 (Workspace 관리 콘솔, 최고 관리자 권한 필요)
1. [admin.google.com](https://admin.google.com/) → **보안 → 액세스 및 데이터 관리 → API 제어 → 도메인 전체 위임 관리**.
2. **새로 추가**:
   - 클라이언트 ID: 1-1의 **고유 ID(숫자)**. 서비스 계정 이메일이 아니다.
   - OAuth 범위: `https://www.googleapis.com/auth/gmail.send`
3. **승인**. 반영까지 보통 몇 분, 길면 24시간 걸린다.

### 1-3. 발신 계정
- `GMAIL_SENDER`는 Workspace의 **실제 사용자 계정**이어야 한다(라이선스가 있고 Gmail 서비스가 켜진 계정). 그룹 주소나 별칭은 대신할 수 없다.
- 발신 표시 이름은 `MAIL_SENDER_NAME`(기본 "오즈코딩스쿨")이다.

### 1-4. 확인
```bash
docker compose exec api python -m app.cli send-test-mail <받는주소>
```
- `MAIL_DRIVER=gmail`, `GMAIL_SENDER`, `GOOGLE_SERVICE_ACCOUNT_JSON`이 있어야 한다.

### 1-5. `unauthorized_client`가 날 때 확인할 것 (현재 상태)
이 오류는 키는 맞지만 **위임이 등록·반영되지 않았다**는 뜻이다. 아래를 차례로 확인한다.
1. 1-2에 넣은 클라이언트 ID가 **지금 쓰는 키 파일의 `client_id`** 와 같은가. 키 JSON의 `client_id` 값과 관리 콘솔에 등록된 ID를 비교한다. 서비스 계정을 새로 만들었다면 ID가 바뀐다.
2. 범위 문자열이 정확히 `https://www.googleapis.com/auth/gmail.send`인가. 앞뒤 공백, 쉼표 구분, `http` 오타가 흔하다. 코드가 요청하는 범위와 **완전히 같아야** 한다(등록 범위보다 많이 요청하면 거부된다).
3. 등록 후 충분히 기다렸는가(최대 24시간).
4. 서비스 계정이 속한 프로젝트가 회사 Workspace 조직 밖(개인 계정 프로젝트)이어도 위임은 가능하다. 다만 조직 정책으로 외부 위임을 막아 두었는지 Workspace 관리자에게 확인한다.
5. `GMAIL_SENDER`가 위임을 등록한 Workspace 도메인의 사용자인가.

---

## 2. 도메인 전체 위임에 Meet·Drive 범위 추가 (P12·P13)

1-2에서 등록한 같은 클라이언트 ID의 범위를 **편집**해 아래를 추가한다(쉼표로 구분해 한 줄로 넣는다).

| 범위 | 용도 |
| --- | --- |
| `https://www.googleapis.com/auth/gmail.send` | 메일 발송 (기존) |
| `https://www.googleapis.com/auth/meetings.space.created` | 멘토링 세션용 Meet 공간 생성·설정 |
| `https://www.googleapis.com/auth/meetings.space.readonly` | 회의 기록(참가·녹화·전사) 조회, Workspace Events 구독 |
| `https://www.googleapis.com/auth/drive.readonly` | Drive에 저장된 녹화·전사 파일 조회·스트리밍 중계 |

함께 확인할 것:
- **Meet 공간을 만드는 계정**(대신할 회사 계정)을 정해야 한다. 녹화 파일은 이 계정의 Drive(`Meet Recordings` 폴더)에 쌓인다. P12 시작 때 결정한다.
- 그 계정의 **Workspace 버전이 Meet 녹화·전사를 지원**하는지 확인한다(Business Standard 이상 등). 관리 콘솔 → **앱 → Google Workspace → Google Meet → Meet 동영상 설정**에서 녹화가 허용돼 있어야 한다.
- 자동 녹화(공간 설정으로 회의 시작 시 녹화)를 쓰려면 해당 버전에서 지원하는지 P12 전에 확인한다.

---

## 3. Google Cloud API 사용 설정 + Pub/Sub (P12)

Meet 회의 시작·종료·녹화 생성 이벤트를 Workspace Events API → Pub/Sub 토픽으로 받고, 워커가 **pull 구독**으로 가져온다(구현 계획 P12).

### 3-1. API 사용 설정 (1-1과 같은 프로젝트)
**API 및 서비스 → 라이브러리**에서 다음을 사용 설정한다.
- Google Meet REST API
- Google Workspace Events API
- Google Drive API
- Cloud Pub/Sub API

### 3-2. 토픽과 구독
```bash
gcloud config set project <PROJECT_ID>
gcloud pubsub topics create oz-meet-events
gcloud pubsub subscriptions create oz-meet-events-pull \
  --topic=oz-meet-events \
  --ack-deadline=60 \
  --message-retention-duration=7d \
  --expiration-period=never
```
- 이름은 예시다. 정한 이름은 P12에서 설정 키(토픽·구독 이름)로 넣는다.
- 로컬·운영을 나누려면 토픽·구독을 환경별로 따로 만든다(예: `oz-meet-events-local`).

### 3-3. 권한
1. **Meet 이벤트 발행 권한:** Workspace Events가 토픽에 메시지를 넣을 수 있게 Google 시스템 계정에 발행 권한을 준다.
   ```bash
   gcloud pubsub topics add-iam-policy-binding oz-meet-events \
     --member="serviceAccount:meet-api-event-push@system.gserviceaccount.com" \
     --role="roles/pubsub.publisher"
   ```
2. **구독 읽기 권한:** 백엔드 서비스 계정(1-1)이 구독에서 메시지를 가져오게 한다.
   ```bash
   gcloud pubsub subscriptions add-iam-policy-binding oz-meet-events-pull \
     --member="serviceAccount:oz-backoffice@<PROJECT_ID>.iam.gserviceaccount.com" \
     --role="roles/pubsub.subscriber"
   ```
   - Pub/Sub은 위임이 아니라 **서비스 계정 자신의 IAM 권한**으로 호출한다.
3. Workspace Events 구독 생성은 Meet 공간 소유 계정을 대신해(위임, 2번의 Meet 범위) 백엔드가 한다. 별도 콘솔 작업은 없다.

### 3-4. 확인 (P12 구현 후)
- 테스트 공간에서 회의를 열고 닫은 뒤 `gcloud pubsub subscriptions pull oz-meet-events-pull --limit=5`로 메시지가 오는지 본다(확인 후에는 백엔드가 가져가도록 ack하지 않는다).

---

## 4. SMS 발송 업체 (P7 어댑터, 별도 PR)

지금은 `SMS_DRIVER=console`로 인증번호를 로그에만 남긴다(A29). 운영(`ENVIRONMENT=production`)에서 console이면 SMS 발송은 503(`sms_not_configured`)이다.

### 4-1. 업체 결정 (사용자 결정 필요)
국내 문자 API 예: NHN Cloud Notification(SMS), Naver Cloud SENS, 솔라피(Solapi), 알리고. 비교할 항목은 다음과 같다.
- 단문(SMS) 건당 단가, 최소 충전·월 기본료
- REST API 인증 방식(API 키·시크릿, HMAC 서명), 발송 IP 허용 목록 요구 여부
- 발송 결과 조회·웹훅, 대량 발송 제한, 장애 이력
- 회사가 이미 쓰는 클라우드·계약이 있으면 그 업체가 정산·관리에 유리하다

### 4-2. 업체가 정해지면 할 일
1. **사업자 회원 가입**과 충전·결제 수단 등록.
2. **발신번호 사전 등록**(전기통신사업법상 필수): 회사 대표번호 등 발신번호를 등록하고, 업체가 요구하는 서류(통신서비스 이용증명원, 사업자등록증 등)를 제출한다. 승인까지 보통 1~3영업일.
3. **API 키·시크릿 발급**. 업체가 IP 허용 목록을 요구하면 로컬 개발 IP와 운영 서버의 고정 출구 IP를 등록한다.
4. 개발팀에 전달: 업체 이름, API 문서 주소, 키·시크릿(비밀 저장소로), 등록된 발신번호. 이후 어댑터 PR에서 `SMS_DRIVER`에 업체 값을 추가하고 설정 키를 `.env.example`에 더한다.
5. 문구는 `[오즈코딩스쿨] 인증번호 123456 (10분 이내 입력)`(A29)로 SMS 한 건 길이 안이다.

---

## 5. Google OAuth 클라이언트 (운영진 로그인)

로컬은 등록돼 있다. 운영 배포 때 아래를 추가한다(A15: 콜백은 백엔드가 받는다).
1. GCP 콘솔 → **API 및 서비스 → 사용자 인증 정보** → 기존 OAuth 2.0 클라이언트 ID(웹 애플리케이션) 편집.
2. **승인된 리디렉션 URI**에 운영 백엔드 콜백 추가: `https://<API 도메인>/api/v1/auth/google/callback`
3. **OAuth 동의 화면**은 사용자 유형 **내부**(회사 Workspace 계정만)로 둔다. `GOOGLE_ALLOWED_DOMAIN`(기본 `nextrunners.co.kr`)으로 한 번 더 막는다.
4. 운영 환경 변수: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`(2의 값).

---

## 6. Airtable (완료)

- Personal Access Token 범위: `data.records:read`, `schema.bases:read`. 대상 Base: KDT 학생관리툴.
- 환경 변수: `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`, `AIRTABLE_STUDENT_TABLE_ID`, `AIRTABLE_BOOTCAMP_TABLE_ID`.
- 토큰을 다시 발급하면 운영 비밀 저장소의 값도 바꾼다.
