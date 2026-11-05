# 결정 기록

프로젝트 진행 중 사용자와 확정한 결정을 모은 문서다. **결정의 단일 출처**이며, 다른 문서와 내용이 다르면 이 문서가 우선한다.
새 결정이 생기면 해당 절에 날짜와 함께 추가한다. 이미 적은 결정을 뒤집을 때는 지우지 말고 `(변경: YYYY-MM-DD → 새 결정)`으로 표시한다.

---

## 1. 통합 범위·방향 (2026-11-03)

| # | 결정 |
| --- | --- |
| D1 | `prev_tools/`의 5개 서비스(Auto_monitor, exam, mentor, ucansign, vacation)를 PostgreSQL 기반의 단일 백오피스로 통합한다. 백엔드(`apps/backend`)와 프론트엔드(`apps/frontend`)를 분리한다 |
| D2 | **멘토링 기능을 먼저 이전한다.** `docs/database_schema_v2.dbml`은 멘토링 이전 범위로 축소된 스키마다. 나머지 서비스(출결 감시, 시험, 전자서명, 수강생 신청서)는 이후 단계에서 테이블을 다시 추가한다 |
| D3 | 수강생도 전원 `users` 계정을 가진다 (이메일 필수). 기존 exam의 링크 인증, vacation의 익명 폼은 이전 시 로그인 기반으로 바꾼다 |
| D4 | 권한은 `user_roles`(범위 기반 RBAC: GLOBAL / BOOTCAMP / COHORT)로 판정하고, `bootcamp_staffs` / `cohort_staffs` / `cohort_mentors`는 담당자 표시용으로 함께 쓴다. 담당자 배정 시 같은 트랜잭션에서 `user_roles`를 동기화한다 |
| D5 | `departments`는 조직도 용도만이다. 데이터 소유 범위는 bootcamp / cohort 기준이다 |
| D6 | HRD-Net 과정 1 : 운영과정(`bootcamps`) N. 같은 HRD 과정에서 파생상품으로 운영과정이 다르게 구성된다 |
| D7 | 파생 기수(`cohorts.parent_id`)는 이번 범위에서 제외한다 |
| D8 | 조교·운영매니저는 내부 직원(`employees`), 멘토·강사는 외부 채용 인원(`users` + `mentors`/`instructors`)이다 |
| D9 | 수강생 신청서(휴가·결석·지각·조퇴·중도포기·출석인정)는 공통 테이블 + 승인 워크플로로 만들고 DB를 원천으로 한다 (후속 단계) |
| D10 | 범위 밖으로 제외: 챕터/과목/기수별 과목, 일반 과제, 프로젝트, 공통 `files` 테이블, 외부 계정(Slack/Discord/ZEP) 테이블. 출결 이전 때 외부 계정을 다시 설계한다 |

## 2. 멘토링 도메인 (2026-11-04 ~ 11-05)

### 예약·신청
| # | 결정 |
| --- | --- |
| M1 | 수강생이 희망 일시 1~3순위로 신청하고 멘토가 하나를 골라 승인한다. 멘토는 요일별 가능 시간(`mentor_availabilities`)과 예외 불가 일정(`mentor_unavailable_periods`)을 등록하며, 희망 일시는 가능 시간 안에서만 고를 수 있다 |
| M2 | 멘토 일정 겹침은 `mentoring_sessions`의 EXCLUDE 제약으로 막는다 (`mentor_id` 비정규화) |
| M3 | 변경 = 기존 신청 취소 + 새 신청 생성(`replaced_request_id`). `CHANGE_REQUESTED` 상태는 없다 |
| M4 | 신청에는 반려 시각·사유, 취소 시각·사유만 기록한다. 채택 일시는 세션의 `starts_at`/`ends_at`이다 |
| M5 | **대리 신청 기능은 없다.** 수강생 본인만 신청한다 |
| M6 | 기수 설정: 팀/1:1 허용 여부, 기본 지급 시간(1:1, 팀), 신청 마감(`min_lead_hours`, 기본 24), 대기 중 신청 수(`max_pending_requests`, 기본 1), 진행 시간 단위(`allowed_duration`, 기본 30분 — 신청 시간은 이 값의 배수, 상한은 잔여 시간) |
| M7 | 기수별 금지 시간대는 기간 + 시간대 + 사유. 요일 지정은 하지 않는다 |

### 시간 계좌
| # | 결정 |
| --- | --- |
| M8 | 계좌는 (수강생 또는 팀) × 기간 유형(평시/프로젝트)으로 나누고, 계좌마다 유효기간(`valid_from`~`valid_until`)을 둔다 |
| M9 | 신청 시 HOLD → 멘토 승인·세션 생성 시 USING → 승인 전 반려·취소 시 RELEASE → 승인 후 취소 시 REFUND (노쇼도 REFUND, M28). 잔여 = total − held − used, **음수 불가** |
| M10 | 원장은 append-only이고 `(request_id, type)` 유니크로 같은 신청의 중복 처리를 막는다. 운영진 지급·조정(STAFF_GRANT / STAFF_ADJUST)만 `request_id`가 없다 |

### 팀·배정·계약·정산
| # | 결정 |
| --- | --- |
| M11 | 팀 번호는 기수 × 유형별로 매긴다. 팀에는 담당 멘토가 고정되며 팀 신청은 담당 멘토에게만 한다. 수강생은 같은 유형의 팀에 하나만 소속된다 |
| M12 | 같은 멘토를 같은 기수·유형에 여러 번 배정할 수 있다. 활성 배정끼리 기간 겹침만 EXCLUDE로 막는다 |
| M13 | 단가(`pay_unit`, `pay_rate`)와 정산 기준은 기수 배정(`cohort_mentors`)에서 관리한다 |
| M14 | 계약(`educator_contracts`)은 체결 여부만 관리한다. 가입 전에도 계약할 수 있어 상대방 정보(이름, 이메일, 연락처)를 기록하고, ~~가입 이메일이 `contractor_email`과 같으면~~ mentors/instructors를 만들고 자동 연결한다. 계약 유형과 연결 컬럼이 일치해야 한다(check) (변경: 2026-11-05 → 매칭 기준은 A6: 이름 + SMS 인증된 휴대폰) |
| M15 | 기수 배정·활성화에는 배정 기간을 포함하는 ACTIVE 계약이 필요하다 (앱 레벨 검증) |
| M16 | 정산은 멘토 × 월 단위(DRAFT → CLOSED)이고, 세션별 명세에 마감 시점 단가·정산 기준을 스냅샷한다. 세션은 한 번만 정산된다 |

### 세션·Meet·녹화
| # | 결정 |
| --- | --- |
| M17 | Google Meet만 쓴다. **Google Calendar 초대는 보내지 않는다** |
| M18 | 세션 진행 상태(IN_PROGRESS)와 실제 시작·종료 시각은 Google Workspace Events(Meet 이벤트)로 받아 저장한다. 이벤트는 Google Cloud Pub/Sub **pull 구독**으로 taskiq 워커가 가져온다 (공개 웹훅 불필요) (보완: 2026-11-05) |
| M19 | 녹화·전사·요약 파일은 회사 계정 Google Drive에 원본을 두고, 멘토에게 Drive 권한을 주지 않는다. 백엔드가 서비스 계정으로 스트리밍 중계한다 (영상은 Range 요청 지원) |
| M20 | 녹화 수집은 이벤트를 기본으로 하고, 보완 폴링은 별도 재시도 컬럼 없이 `recording_status`와 `ends_at`(7일 이내)으로 대상을 고른다 |
| M21 | 개인별 출석은 저장하지 않는다. 진행 여부는 세션 상태(COMPLETED / NO_SHOW)로만 판단한다 |
| M22 | 내부 메모는 멘토 전용, 세션당 1개다. 수강생 응답 스키마에서 제외한다 |

### 채팅·알림·감사
| # | 결정 |
| --- | --- |
| M23 | 채팅방은 1:1(수강생-멘토) 또는 팀(팀원 전체-담당 멘토) 중 하나다. 읽음은 참여자별 마지막 읽은 위치(`mentoring_chat_reads`)로 관리한다 |
| M24 | 신청·승인·반려·취소 **알림은 보류**한다. 다른 알림 방법을 검토 중이며, 확정되면 발송 아웃박스(중복 방지) 테이블을 추가한다 |

### 멘토링 운영 규칙 (2026-11-05)
| # | 결정 |
| --- | --- |
| M26 | 승인된 멘토링은 수강생·멘토가 시작 `min_lead_hours` 전까지만 취소할 수 있다 (전액 REFUND). 그 이후에는 운영진만 취소하며 환불 여부를 선택한다 (환불 안 함이면 USING 유지) |
| M27 | 세션 완료·노쇼는 **멘토의 기록 제출로 확정**한다 (COMPLETED + 실제 진행 시간, 또는 NO_SHOW). Meet 이벤트는 IN_PROGRESS·실제 시각만 반영한다 |
| M28 | **노쇼는 수강생에게 환불**(REFUND)한다 |
| M29 | 노쇼 세션도 멘토 정산에 포함하되, 배정(`cohort_mentors`)별 **노쇼 고정 금액**(`no_show_pay_amount`)으로 정산한다 |
| M30 | 멘토링 정산 단가는 **시급(HOURLY)·회당(PER_SESSION)만** 쓴다. 시급 = 단가 × 정산분 / 60, 회당 = 단가. **원 미만 내림** |
| M31 | 운영진 권한: SUPER_ADMIN 전체 / 매니저(담당 기수) = 가입 승인, 멘토링 설정, 멘토 배정, 시간 지급·조정, 정산 마감, **계약 관리** / 조교(담당 기수) = 조회, 신청 관리(취소), **수강생 가입 승인, 수강생 명단 조회·동기화, 팀 구성, 시간 지급·조정** (조교 권한 추가: 2026-11-05). 상세 표는 `docs/implement_plans/mentoring_phase1_backend.md` |
| M32 | 기존 mentor 서비스(Firestore) 데이터는 1단계에서 이관하지 않는다. 새 기수부터 새 시스템으로 운영한다 |

## 2-1. 계정·인증 (2026-11-05)
| # | 결정 |
| --- | --- |
| A1 | 운영진은 nextrunners.co.kr Google OAuth로 로그인한다 (비밀번호 없음) |
| A2 | 수강생·멘토는 **이메일(@gmail.com만 허용) + 비밀번호**로 가입·로그인한다 |
| A3 | 가입 시 **이메일 인증코드**(소유 확인)와 **휴대폰 SMS 인증**을 모두 거친다. 비밀번호 재설정도 이메일 인증코드로 한다 |
| A4 | 이메일 발송은 회사 Workspace **Gmail API**로 한다. SMS 발송 업체는 **미정**이다 (발송 인터페이스를 두고 로컬은 콘솔 출력) |
| A5 | 수강생 명단은 **Airtable이 원천**이다. taskiq 주기 동기화(+ 운영진 수동 실행)로 백오피스 `students`에 upsert한다(A10, 처음에는 별도 명단 테이블이었음). 필드명은 설정으로 매핑한다 |
| A9 | 명단 동기화는 범위를 나눠 실행할 수 있다: **전체 / 특정 과정 / 특정 기수** (Airtable `filterByFormula`). 주기 동기화와 전체 동기화는 SUPER_ADMIN 범위이고, 매니저·조교는 담당 과정·기수만 동기화한다. 원천 삭제 판정은 실행한 범위 안에서만 한다 (2026-11-05) |
| A10 | 별도 명단 테이블(`student_rosters`)을 두지 않고 **`students`에 합친다**. Airtable 명단 레코드 1건 = 수강 등록 1건이며, 동기화가 `students`에 upsert한다(`airtable_record_id` 유일). 가입 전에는 `students.user_id`가 NULL이고, 가입 시 이름 + 휴대폰으로 대조해 회원을 연결한다(A6). 이름·휴대폰·이메일·HRD 상태는 Airtable이 원천이고, 수강 상태(`status`·종료일·사유)는 백오피스가 관리해 동기화가 덮어쓰지 않는다. 기수를 매핑하지 못한 레코드는 `students`로 만들지 않고 `roster_sync_runs.unmapped_records`(jsonb)에 남긴다. 멘토링 등 기능은 `user_id`가 있는(가입한) 수강생만 대상으로 한다 (2026-11-05) |
| A6 | 자동 승인 기준: 수강생은 명단과 **이름 + 휴대폰**(SMS 인증된 번호)이 일치하면, 멘토는 계약과 **이름 + 휴대폰**이 일치하면 자동 승인한다. 일치하지 않으면 **승인 대기**로 두고, 담당 매니저 이상이 승인한다. 대기 중에는 로그인해도 상태 화면만 볼 수 있다 |
| A7 | 토큰: access는 응답 본문(프론트 메모리, `Authorization` 헤더), refresh는 HttpOnly·Secure·SameSite 쿠키. 갱신할 때 refresh를 회전한다 (Redis 저장) |
| A8 | Google API(Meet, Drive, Gmail, Workspace Events)는 **서비스 계정 + 도메인 전체 위임**으로 회사 계정을 대신해 호출한다 |
| M25 | 처리자·작성자(운영진 시간 지급·조정, 정산 마감, 내부 메모 작성·수정)는 각 테이블에 두지 않고 `audit_logs`로 추적한다 |

## 3. 공통 데이터 규칙

| # | 결정 |
| --- | --- |
| C1 | id는 uuid7. 시각은 timestamptz(UTC 저장), 업무상 하루 경계는 Asia/Seoul |
| C2 | `users.email`은 소문자로 정규화해 저장한다 (check 제약) |
| C3 | ~~객체 저장소는 GCS. DB에는 객체 이름(`*_key`)만 저장하고 조회 시 V4 서명 URL을 발급한다~~ (변경: 2026-11-05 → C5) |
| C5 | 객체 저장소는 **AWS S3**. **비공개 버킷 1개**를 prefix(`contracts/`, `profiles/` …)로 나눠 쓴다. DB에는 객체 키(`*_key`)만 저장하고, 다운로드는 presigned GET URL로만 제공한다(프로필 사진 포함) (2026-11-05) |
| C6 | 업로드는 **presigned POST**로 브라우저가 S3에 직접 올린다. 정책으로 크기 상한·Content-Type을 S3가 강제하고, 업로드 후 서버가 `head_object`로 확인한다 (2026-11-05) |
| C7 | S3 엔드포인트는 설정으로만 바꾼다. 서버 호출용 `S3_ENDPOINT_URL`과 브라우저용 presigned URL 서명 주소 `S3_PUBLIC_ENDPOINT_URL`을 분리한다. 운영은 엔드포인트 없이 AWS 기본값과 IAM 역할을 쓴다 (2026-11-05) |
| C4 | 외부 숫자 ID(Discord snowflake 등)는 문자열로 저장하고 API에서도 문자열로 내보낸다 |

## 4. 백엔드 기술 (2026-11-05)

| # | 결정 |
| --- | --- |
| B1 | 스택: FastAPI, Tortoise ORM(asyncpg), PostgreSQL, Redis, Google OAuth2, PyJWT, ruff, mypy / 테스트: pytest-asyncio, fakeredis, respx, coverage |
| B2 | DDD 바운디드 컨텍스트 7개(identity, access, organization, academy, educator, mentoring, audit) × 4계층(presentation / application / domain / infrastructure) |
| B3 | 패키지 관리자 uv, Python 3.13 |
| B4 | 마이그레이션 aerich. DBML로 표현할 수 없는 제약(EXCLUDE, 부분 유니크, 복합 FK)은 생성된 마이그레이션 파일에 raw SQL로 추가한다 |
| B5 | 작업 큐·스케줄러 taskiq + taskiq-redis |
| B6 | import-linter로 계층·컨텍스트 의존 규칙을 강제한다 |
| B7 | 채팅 실시간 전송 방식(WebSocket / SSE)은 채팅 구현 시점에 결정한다 |
| B8 | S3 클라이언트는 **aioboto3**(asyncio 네이티브). 의존성은 S3 어댑터를 구현할 때 추가한다 (2026-11-05) |
| B9 | Tortoise 모델은 7개 컨텍스트 모듈을 **단일 app `models`** 에 등록한다. 마이그레이션 이력이 하나라 `aerich upgrade` 한 번으로 적용되고, FK는 `"models.UserModel"`처럼 참조한다. 컨텍스트별 app은 이력이 7개로 나뉘고 다른 app 테이블 정의가 마이그레이션에 중복돼 제외했다(실험 확인). 코드 경계는 import-linter가 강제한다 (2026-11-05) |

## 4-1. 저장소 운영 (2026-11-05)

| # | 결정 |
| --- | --- |
| R1 | Git 브랜치·커밋·PR·구현 기록 규칙은 루트 `README.md`를 따른다. **README는 수정할 내용을 사용자에게 확인받은 뒤에 고친다** |
| R2 | 커밋 타입에 `hotfix`(운영 `main` 대상 긴급 수정)를 유지한다. 브랜치는 `main`에서 만든 `fix/` |
| R3 | `main` 병합 시 자동 배포가 원칙이다. 배포 워크플로(`deploy.yml`)는 배포 대상 확정 후 구성한다 |
| R4 | 프론트엔드는 Vercel로 배포한다 |
| R5 | CI는 변경된 앱만 검사한다. 백엔드 CI는 PostgreSQL 서비스 컨테이너로 통합 테스트까지 실행한다 |
| R6 | 로컬 개발의 기본 실행 방식은 docker compose다. 루트 `docker-compose.yml`이 PostgreSQL, Redis, 백엔드 api / worker / scheduler를 띄운다. 백엔드 이미지는 `Dockerfile`의 `dev`(소스 마운트 + reload) / `prod` 타깃으로 나눈다. 호스트 uv 실행은 IDE·디버거용 대안으로 유지한다 (2026-11-05) |
| R7 | 로컬·CI용 S3 에뮬레이터는 **floci**(`floci/floci:2.4.0` 고정, `FLOCI_SERVICES_S3_ENFORCE_AUTH=true`, 로컬은 persistent + 볼륨). LocalStack은 최신 버전이 인증 토큰을 요구하고, MinIO는 커뮤니티 배포가 중단돼 제외했다. MiniStack은 예비 후보다. 근거(2026-11-05 실측): 백오피스가 쓸 S3 시나리오 16개(presigned POST 크기·타입 정책, presigned GET·만료, CORS, 서명 검증, 비공개 버킷, aioboto3, 멀티파트, Range)에서 floci·MiniStack 모두 인증 옵션을 켜면 16/16 통과, 기본값에서는 서명 미검증. floci는 이미지 93MB·유휴 23MiB·첫 응답 0.5초, 옵션 하나로 버킷 설정까지 데이터 유지, 커뮤니티·호환성 테스트 규모와 고정 릴리스 주기(매월 15일·말일)에서 우세 (2026-11-05) |
| R8 | 버킷·CORS 초기화는 에뮬레이터 전용 init 훅이 아니라 compose의 `s3-init`(`amazon/aws-cli`) 원샷 컨테이너가 S3 API로 수행한다 (`infra/s3/`). 에뮬레이터를 바꿔도 그대로 쓴다 (2026-11-05) |

## 5. 프론트엔드 기술 (2026-11-03)

| # | 결정 |
| --- | --- |
| F1 | React + Vite + TS + Tailwind + shadcn/ui + TanStack Query + Zustand + lucide-react + oxlint / 테스트: Vitest + Testing Library + MSW + Playwright E2E (처음부터 적용) |
| F2 | 서버 데이터는 TanStack Query, 클라이언트 전용 상태만 Zustand |

## 6. 미결정·보류

| 항목 | 상태 | 관련 |
| --- | --- | --- |
| 멘토링 알림 방식 | 보류 (사용자 검토 중) | M24 |
| SMS 발송 업체 | 미정 (가입 PR 전에 결정 필요) | A4 |
| Airtable 실제 테이블·필드 구조 | 명단 동기화 구현 전 확인 필요 | A5 |
| `StudentStatus` enum 값 | HRD-Net 실제 상태 코드 확인 필요 | `database_schema_v2.dbml` |
| 채팅 실시간 전송 방식 | 채팅 구현 시 결정 | B7 |
| Meet 참석자 자동 반영 | 하지 않기로 함 (M21). 재검토 시 Google 계정 ID 매칭 조건 참고 | `database_schema_v2_mentoring_review.md` |
