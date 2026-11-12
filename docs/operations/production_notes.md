# 운영 설정 참고사항

운영 배포는 나중에 한 번에 설정한다(2026-11-11 사용자 결정). 그때 빠뜨리지 않도록 지금까지 쌓인 운영 관련 사항을 모아 둔다. 기능을 추가하면서 운영 설정이 새로 생기면 이 문서에 이어서 적는다.
외부 서비스(Google, SMS, Airtable) 준비는 [`external_setup.md`](external_setup.md)를 본다.

## 0. 아직 정하지 않은 것 (배포 전에 결정)

| 항목 | 내용 |
| --- | --- |
| 배포 대상 | 백엔드를 띄울 곳(EC2 + compose, ECS 등). 배포 워크플로 `.github/workflows/deploy.yml`도 이때 만든다(R3) |
| 도메인 | 프론트(Vercel, R4)와 API 도메인. **같은 사이트(같은 상위 도메인)여야 한다** (1-3 참고) |
| PostgreSQL·Redis | 관리형(RDS, ElastiCache 등) 또는 컨테이너. 백업·보존 정책 |
| 비밀 저장소 | 환경 변수를 넣을 곳(AWS Secrets Manager / SSM Parameter Store 등) |
| 업로드 정리 정책 | 확정되지 않은 업로드 객체 정리 방법 (3-4 참고) |
| 로그·모니터링 | 로그 수집, 오류 알림, 헬스체크 대상 |

## 1. 환경 변수 (운영 값)

키 목록의 기준은 `apps/backend/.env.example`이다. 운영에서 로컬과 다르게 넣어야 하는 값만 적는다.

| 키 | 운영 값 | 비고 |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | console 메일·SMS 드라이버면 발송만 503 (A29) |
| `DEBUG` | `false` | |
| `LOG_LEVEL` | `INFO` | |
| `CORS_ORIGINS` | `["https://<프론트 도메인>"]` | JSON 배열 |
| `FRONTEND_BASE_URL` | `https://<프론트 도메인>` | 로그인 후 이동 주소 |
| `DATABASE_URL` | 운영 PostgreSQL | `postgres://user:pass@host:5432/db` |
| `REDIS_URL`, `TASKIQ_REDIS_URL` | 운영 Redis (DB 번호를 나눈다) | 리프레시 토큰·레이트 리밋·락 / 작업 큐 |
| `JWT_SECRET_KEY` | `openssl rand -hex 32`로 새로 만든 값 | 코드 기본값 금지. 바꾸면 모든 세션이 끊긴다 |
| `REFRESH_COOKIE_SECURE` | `true` | |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | OAuth 클라이언트 | |
| `GOOGLE_REDIRECT_URI` | `https://<API 도메인>/api/v1/auth/google/callback` | 콘솔 등록값과 같아야 한다 |
| `GOOGLE_ALLOWED_DOMAIN` | `nextrunners.co.kr` | |
| `AIRTABLE_*` | 운영 토큰·ID | |
| `AWS_REGION` | `ap-northeast-2` | |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | **비운다** | IAM 역할(인스턴스·태스크 역할)을 쓴다 (C7) |
| `S3_BUCKET` | 운영 버킷 이름 | |
| `S3_ENDPOINT_URL`, `S3_PUBLIC_ENDPOINT_URL` | **비운다** | AWS 기본 엔드포인트 (C7) |
| `TRUSTED_PROXIES` | nginx·로드밸런서 주소(IP·CIDR) JSON 배열 | 비우면 레이트 리밋이 프록시 IP 하나로 묶인다 (1-2) |
| `MAIL_DRIVER` | `gmail` | |
| `GMAIL_SENDER`, `GOOGLE_SERVICE_ACCOUNT_JSON` | 운영 발신 계정, 서비스 계정 키 JSON(한 줄) | |
| `SMS_DRIVER` | 업체 어댑터 값 | 업체 확정 전에는 `console` → SMS 503 |

### 1-1. 비밀 값
- `JWT_SECRET_KEY`, `GOOGLE_CLIENT_SECRET`, `AIRTABLE_TOKEN`, `GOOGLE_SERVICE_ACCOUNT_JSON`, SMS 키, DB·Redis 비밀번호는 비밀 저장소에만 둔다. 이미지·저장소·로그에 남기지 않는다.

### 1-2. 프록시와 클라이언트 IP
- 레이트 리밋(가입 인증코드, 로그인 잠금)은 클라이언트 IP를 쓴다. 백엔드는 `TRUSTED_PROXIES`에 있는 주소에서 온 요청만 `X-Forwarded-For`를 믿는다.
- nginx는 `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`, `X-Forwarded-Proto $scheme`, `Host $host`를 넘긴다. 앞에 로드밸런서가 있으면 그 대역도 `TRUSTED_PROXIES`에 넣는다.

### 1-3. 쿠키와 도메인
- refresh 쿠키와 OAuth state 쿠키는 `HttpOnly; Secure; SameSite=Lax`다. 프론트에서 API를 `credentials: "include"`로 부를 때 쿠키가 실리려면 **프론트와 API가 같은 사이트**여야 한다(예: `app.<도메인>` + `api.<도메인>`). `*.vercel.app` 기본 도메인과 다른 API 도메인 조합은 쿠키가 실리지 않는다 → Vercel에 회사 도메인을 연결한다.

## 2. 백엔드 실행 구성

| 구성 | 명령·설정 |
| --- | --- |
| 이미지 | `apps/backend/Dockerfile`의 `prod` 타깃 (의존성만 설치, `uvicorn app.main:app --host 0.0.0.0 --port 8000`) |
| api | 여러 대로 늘려도 된다. 헬스체크 `GET /health` |
| worker | `taskiq worker app.workers.broker:broker <작업 모듈들>` |
| scheduler | `taskiq scheduler app.workers.broker:scheduler <작업 모듈들>` — **반드시 1대만** 띄운다(여러 대면 정기 작업이 중복 실행된다) |

### 2-1. 작업 모듈 목록 (worker·scheduler 둘 다)
새 작업 모듈이 생기면 여기에 추가한다. 빠지면 그 작업이 등록되지 않는다.
```text
app.workers.tasks.roster          # 명단 동기화 (매시간), 수동 동기화 실행
app.workers.tasks.contracts       # 계약 만료 (매일 00:05 KST)
app.workers.tasks.notifications   # 메일 발송 (재시도 3회)
app.workers.tasks.mentoring       # 기수 멘토 배정 만료 (매일 00:00 KST), 대기 신청 만료 (10분마다), 수강 종료 처리
```
- 로컬은 루트 `docker-compose.yml`에 반영돼 있다. 저장소 밖의 `docker-compose.prod.yml`(현재 빈 파일)에는 아직 없다.

### 2-2. nginx
- `infra/nginx/prod.conf`(현재 빈 파일, 저장소 밖)에 작성한다: TLS 종료, `/api/` → api:8000 프록시, 1-2의 헤더, 업로드는 S3 presigned POST로 직접 가므로 큰 `client_max_body_size`는 필요 없다.
- 녹화 스트리밍 중계(P13)는 `Range` 요청을 그대로 넘기고 응답 버퍼링을 끈다(`proxy_buffering off;`).

## 3. AWS S3

### 3-1. 버킷
- 비공개 버킷 1개(C5). **퍼블릭 액세스 차단 4개 모두 켬**, 기본 암호화 SSE-S3, 버전 관리는 선택.
- prefix: `contracts/`(계약서 PDF), `profiles/`(멘토 사진). 이후 기능이 prefix를 추가하면 여기에 적는다.

### 3-2. CORS
브라우저가 presigned POST로 직접 올리고 presigned GET으로 내려받는다. 로컬 설정(`infra/s3/cors.json`)과 같은 형식으로 운영 프론트 도메인을 넣는다.
```json
{
  "CORSRules": [
    {
      "AllowedOrigins": ["https://<프론트 도메인>"],
      "AllowedMethods": ["GET", "HEAD", "POST"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3000
    }
  ]
}
```

### 3-3. IAM 역할 (api·worker에 연결)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::<버킷>/*"
    }
  ]
}
```
- presigned URL은 이 역할의 권한으로 서명된다. `head_object`는 `s3:GetObject`로 된다.
- 임시 자격 증명으로 서명한 URL은 자격 증명이 만료되면 함께 무효가 된다. presigned 만료는 10분(`S3_PRESIGNED_*_TTL_SECONDS`)이라 문제없다.

### 3-4. 수명 주기 규칙
- **미완료 멀티파트 업로드 정리**(1일)는 바로 건다.
- **확정되지 않은 업로드**(업로드 URL만 받고 확정하지 않은 객체)와 버려진 계약서 객체 정리는 **결정이 필요하다**. 지금은 업로드 키가 최종 prefix(`contracts/`, `profiles/`)에 바로 만들어져 수명 주기 규칙만으로 미확정 객체를 골라낼 수 없다. 선택지: 임시 prefix(`uploads/tmp/`)에 올리고 확정할 때 복사 + 임시 prefix 1일 만료 규칙 / 확정 때 객체 태그를 달고 태그 없는 객체 만료 / 주기 정리 작업. 배포 전에 정한다(구현 기록 26·28·29의 남은 작업).

## 4. 데이터베이스와 첫 배포 순서

1. 운영 DB를 만들고 `DATABASE_URL`을 넣는다. 로컬 개발용 `infra/postgres/init` SQL(테스트 DB 생성 등)은 운영에 쓰지 않는다.
   - **`btree_gist` 확장을 먼저 만든다**: `CREATE EXTENSION IF NOT EXISTS btree_gist;` (마이그레이션의 EXCLUDE 제약 — 금지 시간대·가능 시간 겹침, 이후 세션 겹침 — 에 필요. 로컬은 init SQL이 만든다). RDS는 마스터 사용자로 실행할 수 있다.
2. 마이그레이션: `aerich upgrade` (api 이미지로 일회성 실행). 이후 배포마다 api를 띄우기 전에 실행한다.
3. 역할·권한 시드: `python -m app.cli seed-roles` (멱등). **역할·권한 정의가 바뀐 배포마다** 실행한다. 판정은 코드 기준이라 시드 전에도 동작하지만 DB 사본을 맞춘다(A16). 예: P8-2에서 TEAM_LEAD·`mentor.manage`·`staff.assign` 추가.
4. 최고 관리자: `python -m app.cli create-super-admin <회사 이메일> [--name 이름]` (멱등, A14).
5. 메일 확인: `python -m app.cli send-test-mail <받는주소>`.
6. 명단 동기화: 첫 동기화는 운영진 화면(수동 실행) 또는 매시간 작업으로 돈다.
7. worker·scheduler를 띄우고 로그에서 2-1의 모듈이 모두 `Importing tasks from module ...`으로 나오는지 확인한다.

### 4-1. 마이그레이션 되돌리기
- `aerich downgrade -v <번호>`는 테이블을 지운다. 운영에서는 백업을 먼저 받고 실행한다. 각 PR 본문 "참고 사항"에 되돌리는 방법을 적어 두었다.

## 5. 정기 작업 시각 (KST)

| 작업 | 시각 | 비고 |
| --- | --- | --- |
| `mentoring.assignments.expire` | 매일 00:00 | 종료일이 지난 기수 멘토 배정 비활성화 |
| `educator.contracts.expire` | 매일 00:05 | 종료일이 지난 계약 ENDED |
| `academy.roster_sync.scheduled` | 매시간 | Airtable 설정이 없으면 건너뜀 |
| `mentoring.requests.expire` | 10분마다 | 승인 가능한 희망 일시가 남지 않은 대기 신청 취소·보류 시간 반환 |

- 모두 멱등이라 scheduler가 멈췄다 다시 떠도 밀린 대상을 처리한다. 매일 작업은 서버 시간대와 무관하게 `cron_offset=Asia/Seoul`로 동작한다(10분마다·매시간 작업은 시간대와 무관).

## 6. 변경 이력
- 2026-11-11: 문서 작성 (P8까지 반영)
- 2026-11-12: 대기 신청 만료 작업 추가 (P11-1)
