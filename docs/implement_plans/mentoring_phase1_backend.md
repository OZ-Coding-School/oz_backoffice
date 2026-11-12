# 멘토링 1단계 백엔드 상세 구현계획

- 작성일: 2026-11-05
- 상태: 계획 확정, 구현 전
- 범위: 멘토링 기능의 백엔드(`apps/backend`). 프론트엔드는 별도 문서로 작성한다.
- 기준 문서: `docs/decisions.md`(결정), `docs/database_schema_v2.dbml`(스키마), `docs/implement_plans/backend_architecture.md`(구조), `apps/backend/CLAUDE.md`(작업 하네스)

---

## 0. 범위

### 포함
- 마스터 데이터(조직·과정·기수·수강생)와 운영진 관리 API
- 인증: 운영진 Google OAuth, 수강생·멘토 이메일+비밀번호 가입(이메일·SMS 인증), 자동 승인·승인 대기
- 권한(RBAC + 범위), 감사 로그
- Airtable 수강생 명단 동기화
- 교육 인력·계약 관리(계약서 S3 업로드)
- 멘토링: 기수 설정, 멘토 배정, 멘토 일정, 팀, 시간 계좌, 신청·승인·취소, Meet 연동, 기록·내부 메모, 녹화 수집·중계, 정산, 채팅

### 제외
| 항목 | 이유 | 근거 |
| --- | --- | --- |
| 기존 mentor 서비스 데이터 이관 | 새 기수부터 새 시스템으로 운영 | M32 |
| 신청·승인 등 **알림** | 알림 방식 검토 중 (보류) | M24 |
| 프론트엔드 | 별도 계획 문서 | — |
| 출결·시험·전자서명·신청서 | 후속 단계 | D2 |

---

## 1. 적용되는 주요 결정 (요약)

| 영역 | 결정 | 번호 |
| --- | --- | --- |
| 운영진 로그인 | nextrunners.co.kr Google OAuth | A1 |
| 수강생·멘토 로그인 | @gmail.com 이메일 + 비밀번호 | A2 |
| 가입 인증 | 이메일 인증코드 + SMS 인증. 비밀번호 재설정은 이메일 인증코드 | A3 |
| 발송 | 이메일은 Gmail API(회사 Workspace). **SMS 업체 미정** | A4 |
| 수강생 명단 | Airtable 원천, taskiq 주기 동기화 + 수동 실행, 필드명은 설정 매핑. 명단 레코드 = `students` 행(가입 전 `user_id` NULL) | A5, A10 |
| 자동 승인 | 수강생은 명단, 멘토는 계약과 **이름 + 휴대폰**이 일치하면 자동 승인. 아니면 승인 대기 → 담당 매니저 이상이 승인 | A6 |
| 토큰 | access는 응답 본문, refresh는 HttpOnly 쿠키 + 회전(Redis) | A7 |
| Google API | 서비스 계정 + 도메인 전체 위임 | A8 |
| Meet 이벤트 | Workspace Events → Pub/Sub **pull 구독**을 워커가 처리 | M18 |
| 취소 | 시작 `min_lead_hours` 전까지 수강생·멘토가 취소(환불). 이후는 운영진만(환불 선택) | M26 |
| 완료·노쇼 | 멘토 기록 제출로 확정. 노쇼는 수강생 환불 | M27, M28 |
| 정산 | 시급·회당만, 원 미만 내림. 노쇼는 배정별 고정 금액 | M29, M30 |
| 저장소 | S3 비공개 버킷 1개 + prefix, presigned POST/GET, aioboto3, 로컬 floci | C5~C7, B8, R7 |

---

## 2. 공통 규약

### 2.1 API
- 경로: `/api/v1/...`. 운영진 전용은 `/api/v1/admin/...`, 본인 리소스는 `/api/v1/me/...`.
- 인증: `Authorization: Bearer <access>`. refresh는 쿠키 `oz_refresh`(HttpOnly, Secure, SameSite=Lax, Path=`/api/v1/auth`).
- 오류: `{"error": {"code", "message"}}`. 도메인 오류 코드는 PR마다 정의한다(예: `insufficient_balance`, `outside_mentor_availability`).
- 목록: `limit`(최대 100) / `offset`. 계속 쌓이는 데이터(채팅, 원장, 감사 로그, 동기화 이력)는 커서(`before`=uuid7) 방식.
- 시각: 요청·응답 모두 ISO 8601 + 타임존. 서버는 UTC로 저장한다.
- 응답 스키마는 역할별로 나눈다. 예: 세션 응답에서 내부 메모는 멘토·운영진 스키마에만 포함한다.

### 2.2 승인 상태 게이트
- `approval_status != APPROVED`인 사용자는 `/api/v1/me`(상태 조회), `/api/v1/auth/*`만 호출할 수 있다.
- 공통 의존성: `require_approved_user`. 나머지 API는 이 의존성을 기본으로 붙인다.

### 2.3 권한표 (M31)

역할 코드: `SUPER_ADMIN`(GLOBAL), `TEAM_LEAD`(GLOBAL, A36), `COHORT_MANAGER`(BOOTCAMP / COHORT 범위), `COHORT_ASSISTANT`(BOOTCAMP / COHORT 범위), `MENTOR`, `STUDENT`

| 권한 코드 | SUPER_ADMIN | 팀리드 | 매니저 | 조교 | 비고 |
| --- | :-: | :-: | :-: | :-: | --- |
| `org.manage` (부서·직위·직원·과정·HRD·기수 관리) | ✅ | | | | |
| `role.assign` (역할 직접 부여, 운영진 가입 승인) | ✅ | | | | 담당자 배정은 `staff.assign`으로 분리(A36) |
| `staff.assign` (과정·기수 담당자 배정) | ✅ | ✅ | | | A36 |
| `user.approve` (가입 승인·반려, 수동 매칭) | ✅ | ✅ | ✅ | ✅ | 매니저·조교는 담당 범위의 수강생만. 멘토 승인은 `contract.manage` 권한자 |
| `roster.sync` (명단 동기화 실행·명단·이력 조회) | ✅ | ✅ | ✅ | ✅ | 매니저·조교는 **담당 범위의 과정·기수만 동기화**하고 그 명단만 조회한다. 전체 동기화와 기수 매핑 실패 명단(`unmapped`) 조회는 전체 범위만 (주기 동기화는 전체) |
| `contract.manage` (계약·계약서, 멘토/강사 연결) | ✅ | ✅ | ✅ | | 계약은 기수 범위가 없으므로 매니저 역할이 하나라도 있으면 허용 |
| `mentor.manage` (멘토 목록·프로필 대리 수정·활성화) | ✅ | ✅ | ✅ | | A36. 범위가 하나라도 있으면 허용 |
| `mentoring.settings.manage` (기수 설정, 금지 시간대) | ✅ | ✅ | ✅ | | |
| `mentoring.assignment.manage` (멘토 배정·단가) | ✅ | ✅ | ✅ | | |
| `mentoring.team.manage` (팀 구성) | ✅ | ✅ | ✅ | ✅ | 매니저·조교는 담당 범위의 팀만 |
| `mentoring.balance.grant` (시간 지급·조정) | ✅ | ✅ | ✅ | ✅ | 매니저·조교는 담당 범위의 수강생 또는 팀만 |
| `mentoring.request.read` (신청·세션 조회) | ✅ | ✅ | ✅ | ✅ | |
| `mentoring.request.cancel` (운영진 취소, 환불 선택) | ✅ | ✅ | ✅ | ✅ | |
| `mentoring.settlement.close` (정산 집계·마감·조회) | ✅ | ✅ | ✅ | | |

- 범위 판정: COHORT 범위 권한은 그 기수에만, BOOTCAMP 범위 권한은 그 과정의 모든 기수에 적용된다. GLOBAL은 전체다.
- 멘토·수강생 기능은 권한 코드가 아니라 **소유 관계**로 검사한다(본인 신청, 본인 배정 기수, 본인 세션). 서비스 계층에서 확인한다.
- 역할·권한은 시드 스크립트(`scripts/seed_roles.py`)로 넣는다. 멱등이어야 한다.

### 2.4 외부 연동 어댑터와 드라이버
모든 외부 연동은 `app/integrations/`의 인터페이스(Protocol) + 구현으로 둔다. 로컬과 테스트에서 쓸 드라이버를 설정으로 고른다.

| 연동 | 인터페이스 | 운영 구현 | 로컬·테스트 |
| --- | --- | --- | --- |
| 이메일 | `EmailSender` | Gmail API (DWD, `gmail.send`) | `console`(로그 출력) / 테스트는 메모리 수집 |
| SMS | `SmsSender` | **업체 미정** | `console` / 메모리 수집 |
| Airtable | `AirtableClient` | Airtable REST(httpx, PAT) | respx 고정 응답 |
| S3 | `ObjectStorage` | aioboto3 | floci (통합 테스트) |
| Google Meet / Drive / Events | `MeetClient`, `DriveClient`, `WorkspaceEventsClient` | Google API (DWD) | respx / 가짜 구현 |
| Pub/Sub | `EventSubscriber` | Pub/Sub pull | 가짜 구현(메모리 큐) |

설정 키 추가(PR마다 해당 키만): `EMAIL_DRIVER`, `SMS_DRIVER`, `GOOGLE_SERVICE_ACCOUNT_FILE`, `GOOGLE_DELEGATED_USER`, `GMAIL_SENDER`, `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_ID`, `AIRTABLE_FIELD_MAP`(JSON), `PUBSUB_SUBSCRIPTION`, `GOOGLE_CLOUD_PROJECT`.

### 2.5 백그라운드 작업 (taskiq)
| 작업 | 주기 | PR |
| --- | --- | --- |
| Airtable 명단 동기화 | 1시간 (+ 수동) | P5 |
| Meet Space 생성 재시도 | 승인 직후 enqueue, 실패 시 지수 백오프 | P12 |
| Pub/Sub 이벤트 pull·처리 | 30초 | P12 |
| 녹화 보완 폴링 (`recording_status` + `ends_at` 7일) | 1시간 | P13 |
| 기록 미제출 세션 표시용 집계 | 화면 조회 시 계산 (작업 없음) | — |

- 같은 작업이 겹쳐 실행되지 않도록 Redis 락(`oz:lock:<작업>`)을 건다.
- 작업은 `app/workers/tasks/`의 얇은 래퍼이고, 로직은 application 서비스에 둔다.

---

## 3. 스키마 변경 (2026-11-05 반영 완료)

`docs/database_schema_v2.dbml`에 반영했다 (테이블 41개).

| 대상 | 변경 | 근거 |
| --- | --- | --- |
| `users` | `approval_status`(PENDING / APPROVED / REJECTED), `approved_at`, `email_verified_at`, `phone_verified_at` 추가, `phone_number` unique | A3, A6 |
| `roster_sync_runs` (신규) | 동기화 실행 이력. 기수 매핑 실패 레코드는 `unmapped_records`(jsonb) | A5, A10 |
| `educator_contracts` | `contractor_phone` 필수, `contractor_email` 선택, (이름, 휴대폰) 인덱스 | A6, M14 변경 |
| `cohort_mentors` | `no_show_pay_amount` 추가, `pay_unit`은 HOURLY / PER_SESSION만 (check) | M29, M30 |
| `mentoring_settlement_items` | `item_type`(SESSION / NO_SHOW) 추가 | M29 |

인증코드(이메일·SMS)와 refresh 토큰은 DB가 아니라 **Redis**에 둔다(TTL).

---

## 4. PR 계획

순서는 의존 관계 기준이다. 각 PR은 `apps/backend/CLAUDE.md`의 커밋·PR 단위와 완료 기준을 따른다.
표기: 🔒 = 선행 준비물(외부 설정·결정)이 필요한 PR.

```text
P1 마스터 모델 ─┬─ P2 인증 기반·운영진 로그인 ─ P3 권한 ─┬─ P4 조직·과정·기수 관리 API
               │                                        ├─ P5 Airtable 명단 동기화 🔒
               │                                        └─ P6 S3 + 교육 인력·계약
               └──────────────── P7 수강생·멘토 가입 🔒 (P5, P6 이후)
P8 기수 설정·멘토 배정 ─ P9 멘토 일정 ─ P10 팀·시간 계좌 ─ P11 신청·승인·취소
 ─ P12 Meet 연동 🔒 ─ P13 기록·메모·녹화 ─ P14 정산 ─ P15 채팅 (B7 결정 후)
```

---

### P1. 마스터 데이터 모델과 첫 마이그레이션
- **목표:** 공통 마스터 테이블을 만들고 마이그레이션 체계를 가동한다.
- **PR 분할 (하네스 규칙: PR 600줄 안팎, PR당 마이그레이션 1개):**
  - P1-1: identity(`users`, `oauth_accounts`) + audit(`audit_logs`) + 첫 마이그레이션 + 통합 테스트 픽스처를 마이그레이션 적용으로 전환
  - P1-2: academy (organization의 담당자 테이블이 `bootcamps`·`cohorts`를 FK로 참조하므로 academy를 먼저)
  - P1-3: organization
- **테이블:**
  - identity: `users`, `oauth_accounts`
  - organization: `departments`, `employee_positions`, `employees`, `bootcamp_staffs`, `cohort_staffs`
  - academy: `hrd_net_bootcamps`, `hrd_net_bootcamp_cohorts`, `bootcamps`, `cohorts`, `students`, `roster_sync_runs` (명단은 `students`에 합침, A10)
  - audit: `audit_logs`
- **작업:**
  - 컨텍스트별 Tortoise 모델, 매퍼, 리포지토리(애그리거트 루트 단위)
  - `aerich init-db` → 첫 마이그레이션. 생성된 파일에 raw SQL 추가: `departments (parent_id, name)` NULLS NOT DISTINCT 유니크 등 DBML note 항목
  - `tests/conftest.py`의 통합 DB 픽스처를 `generate_schemas`에서 **aerich 마이그레이션 적용**으로 교체 (TODO 해소)
  - `AuditRecorder`(audit 컨텍스트 application 서비스)
- **테스트:**
  - 통합: 모델별 저장·조회 왕복, check 제약(`email = lower(email)`, `approved_at` 정합, 기간 check)이 위반 시 실패하는지
  - 단위: 도메인 엔티티 불변식(기수 기간, 수강 상태 전이)
- **API:** 없음 (공통 기반 PR로 예외 허용)

### P2. 인증 기반과 운영진 로그인
- **목표:** 토큰 발급·갱신·폐기, 운영진 Google OAuth 로그인, 운영진 최초 정보 입력(신청). 흐름은 decisions A11·A12.
- PR을 둘로 나눈다.

#### P2-1. 인증 기반과 Google 로그인
- **작업:**
  - refresh 토큰 저장소(Redis): `oz:identity:refresh:<jti>` → user_id, TTL 14일. 갱신할 때 기존 jti를 폐기하고 새로 발급(회전). 폐기된 jti가 다시 쓰이면(`oz:identity:refresh-used:<jti>`) 해당 사용자의 refresh를 전부 폐기(탈취 감지)
  - Google OAuth(Authorization Code + PKCE, state는 Redis 10분·1회용 + 브라우저 쿠키로 대조, **콜백은 백엔드가 받는다** A15): 콜백에서 ID 토큰 클레임 검증(A13) → `hd`·이메일 도메인이 `nextrunners.co.kr`인지 확인 → `oauth_accounts`로 사용자 찾기, 없으면 같은 이메일 회원에 연결하거나 **PENDING 회원 생성**(A11)
  - 탈퇴·정지(승인 후 비활성) 계정은 로그인·갱신 거부(`account_disabled`)
  - 의존성: `get_current_user`, `require_approved_user` (`access.presentation.dependencies`, B10)
- **API:**
  | 메서드 | 경로 | 설명 |
  | --- | --- | --- |
  | GET | `/api/v1/auth/google/login` | 브라우저 이동용. state 쿠키 설정 후 Google로 302. 클라이언트 미설정이면 503 |
  | GET | `/api/v1/auth/google/callback` | Google이 돌려보내는 곳. state 대조 → code 교환 → refresh 쿠키 → 프론트로 302 (실패 시 `/login?error=<code>`) |
  | POST | `/api/v1/auth/refresh` | refresh 쿠키로 회전 갱신 → access(본문). 로그인 직후와 페이지 로드 시에도 이걸로 access를 받는다 |
  | POST | `/api/v1/auth/logout` | refresh 폐기, 쿠키 삭제 |
  | GET | `/api/v1/me` | 내 정보, 승인 상태 (역할은 P3에서 추가) |
- **테스트:** respx로 Google 토큰 응답 고정. 도메인 외 계정 거부, ID 토큰 클레임 검증, refresh 회전, 재사용 탐지, 만료, PENDING 게이트.

#### P2-2. 운영진 최초 정보 입력
- **테이블:** `employee_registrations`(신청자, 부서, 직위, 고용 형태, 상태, 검토 시각, 반려 사유. 회원당 PENDING 하나), `employee_registration_assignments`(역할 MANAGER/ASSISTANT + 과정 또는 기수, 중복 불가)
- **작업:**
  - 최초 로그인한 운영진(도메인 이메일)이 부서·직위·고용 형태·담당(0~20개)을 입력해 신청한다. 대기 중이면 같은 신청을 고치고, 반려됐으면 새 신청을 만든다(이력 보존). 이미 승인된 계정은 409
  - 담당으로 고를 수 있는 것: 활성 과정, 준비·진행 중 기수(활성 과정 소속). academy 공개 서비스 `AcademyCatalog`로 조회·검증
- **API:**
  | 메서드 | 경로 | 설명 |
  | --- | --- | --- |
  | GET | `/api/v1/me/staff-registration/options` | 부서·직위·고용 형태·담당 역할·과정·기수 선택지 |
  | GET | `/api/v1/me/staff-registration` | 내 최근 신청 (없으면 null) |
  | PUT | `/api/v1/me/staff-registration` | 신청·수정 |
  - PENDING도 호출 가능(§2.2의 `/me` 범위). 운영진 도메인 계정이 아니면 403 `not_staff_account`
- **승인·반려는 P3**(A12)

### P3. 권한
- **목표:** RBAC와 범위 검사, 담당자 배정 동기화.
- **테이블:** `roles`, `permissions`, `role_permissions`, `user_roles`
- **작업:**
  - `require_permission(code, scope_from=...)` 의존성. 경로의 `cohort_id`·`bootcamp_id`로 범위를 판정하고, BOOTCAMP 범위는 하위 기수에도 적용한다
  - 권한 판정 결과는 요청 단위로 캐시한다(사용자 역할 1회 조회)
  - 담당자 배정(`bootcamp_staffs`, `cohort_staffs`)과 `user_roles`를 같은 트랜잭션에서 동기화 (D4)
  - **운영진 가입 승인·반려(A11·A12):** 어드민이 신청 항목(부서·직위·고용 형태·담당)을 조정해 승인하면 `employees`·`bootcamp_staffs`·`cohort_staffs`·`user_roles`를 만들고 회원을 APPROVED로 바꾼다. 반려 사유는 감사 로그
- PR을 나눈다.
  - **P3-1 (구현 기록 10):** 역할·권한 테이블, §2.3 권한표 코드 정의(`access/domain/catalog.py`)와 시드(`python -m app.cli seed-roles`, 멱등), 최고 관리자 CLI(`python -m app.cli create-super-admin <email>`, A14), `/me` 역할 목록
  - **P3-2a (구현 기록 13):** `PermissionChecker`(범위 판정, A16)와 `require_permission(code, cohort_param= | bootcamp_param= | any_scope=)` 의존성
  - **P3-2b (구현 기록 14):** 운영진 가입 승인·반려 API. 승인은 한 트랜잭션에서 신청 승인(어드민 조정) → 직원 생성·갱신 → 담당자 추가 → 역할 부여(매니저 → COHORT_MANAGER, 조교 → COHORT_ASSISTANT, 범위 = 담당 과정·기수) → 회원 승인 → 감사 로그. 반려는 사유를 남기고 승인 대기 회원을 REJECTED로 바꾼다(재신청 가능)
  - **P3-3a (구현 기록 15):** 과정·기수 담당자 배정·해제 API. 배정하면 역할 부여, 해제하면 역할 회수(같은 트랜잭션, D4)
  - **P3-3b (구현 기록 16):** 회원 역할 관리 API (`/admin/users/{id}/roles`). 직접 관리 역할은 SUPER_ADMIN뿐이고 마지막 최고 관리자는 회수 불가 (A17)
- **API:**
  | 메서드 | 경로 | 권한 |
  | --- | --- | --- |
  | GET/POST | `/api/v1/admin/cohorts/{id}/staffs` · DELETE `/{staff_id}` | `role.assign`. 배정 = 역할 부여, 해제 = 역할 회수 |
  | GET/POST | `/api/v1/admin/bootcamps/{id}/staffs` · DELETE `/{staff_id}` | `role.assign`. 위와 같음 (과정 범위 역할) |
  | GET/POST | `/api/v1/admin/users/{id}/roles` · DELETE `/{user_role_id}` | `role.assign`. 직접 부여·회수는 SUPER_ADMIN만(A17), 목록은 모든 역할(만료 포함, `managed_by` 표시) |
  | GET | `/api/v1/admin/staff-registrations?status=&limit=&offset=` | 운영진 가입 신청 목록(신청자 포함). `role.assign` (SUPER_ADMIN) |
  | GET | `/api/v1/admin/staff-registrations/{id}` | 신청 상세. `role.assign` |
  | POST | `/api/v1/admin/staff-registrations/{id}/approve` · `/reject` | 항목 조정 후 승인 / 반려 사유. `role.assign` (SUPER_ADMIN) |
- **테스트:** 권한표 전 항목을 매개변수화 테스트(역할 × 권한 × 범위: 허용 / 403). 범위 밖 기수 접근 403.

### P4. 조직·과정·기수 관리 API
- **목표:** 운영진이 마스터 데이터를 관리한다.
- **API (권한 `org.manage`):** 부서·직위·직원, HRD 과정·회차, 운영과정(`bootcamps`), 기수(`cohorts`) CRUD. ~~기수는 `bootcamp.hrd_net_bootcamp_id = hrd_net_cohort.hrd_net_bootcamp_id`를 검증한다~~ → 기수는 다른 HRD 과정의 회차에도 연결된다(D6 보완, 2026-11-09)
- **테스트:** 기수 번호 중복, 기간 역전, HRD 회차 불일치 거부.
- PR을 나눈다.
  - **P4-1 (구현 기록 17):** 조직 — `/admin/departments`, `/admin/positions`(목록·생성·PATCH·삭제), `/admin/employees`(목록·상세·이동). 부서는 상위 안 이름 유일·여러 단계 순환 금지, 참조 중인 부서·직위 삭제는 409 `in_use`. 직원 생성은 가입 승인으로만 한다
  - **P4-2 (구현 기록 18):** 학사 — `/admin/hrd-bootcamps`(+`/{id}/cohorts`), `/admin/hrd-cohorts/{id}`, `/admin/bootcamps`(+`/{id}/cohorts`, `include_inactive`), `/admin/cohorts/{id}`. 기수의 HRD 회차는 운영과정과 같은 HRD 과정이어야 한다(422 `hrd_cohort_mismatch`). 소속 FK는 수정 불가, 운영 중단은 삭제 대신 비활성·상태 변경

### P5. Airtable 수강생 명단 동기화 🔒
- **선행 준비:** Airtable PAT(읽기 권한), 베이스·테이블 ID, **실제 필드 구조 확인 → `AIRTABLE_FIELD_MAP` 확정** — 확인 완료(2026-11-09, 구현 기록 19)
- **테이블 변경 (2026-11-09, A20):** 같은 Base의 수강생 테이블과 과정-기수 테이블을 쓴다. 동기화 실행은 과정-기수 테이블로 HRD 과정·회차·운영과정·기수를 먼저 맞춘 뒤 수강생을 맞춘다(P5-3, 구현 기록 23). 수강생은 `취업운영시트 link`로 기수를 찾는다(P5-4, A21, 구현 기록 25)
- **(이전) 실제 구조 (KDT 학생관리툴 Base, 수강생 정보 시트):** `이름`, `전화번호`(`010-1234-5678`), `이메일`, `기수`(lookup 리스트, `"<과정 별칭> <N>기"`), `상태`(운영 상태), `HRD상태`, `중도탈락일`, `훈련시작일`·`훈련종료일`. 과정 별칭은 `bootcamps.airtable_cohort_prefix`(A18), 수강 상태는 `상태`를 따른다(A19)
- **범위 수식 (실데이터로 검증):** 기수 `ARRAYJOIN({기수})='헬스케어 3기'`, 과정 `FIND('헬스케어 ', ARRAYJOIN({기수}))=1`, 전체 = 별칭이 설정된 과정들의 OR
- PR을 나눈다. **P5-1 (구현 기록 19):** `airtable_cohort_prefix`, pyairtable 클라이언트(B11). **P5-2a (구현 기록 20):** 레코드 해석·상태 매핑·동기화 서비스. **P5-2b (구현 기록 21):** Airtable 원천 어댑터, 동시 실행 락, taskiq 작업(수동 실행·매시 전체). **P5-2c (구현 기록 22):** 관리 API(동기화 요청 → taskiq 전달·202, 실행 이력 커서·담당 범위 필터, 기수 명단, 실패 목록)
- 실패 목록(unmapped_records) 사유: `cohort_not_found`(별칭은 설정됐지만 DB에 그 기수가 없음), `cohort_changed`(레코드의 기수가 바뀜, 자동 이동 안 함), `invalid_name`. 기수가 비었거나 별칭이 설정되지 않은 과정의 레코드는 건너뛴다(대상 아님)
- **목표:** Airtable을 원천으로 `students`(수강 등록 = 명단 레코드, A10)를 최신으로 유지한다.
- **작업:**
  - `AirtableClient`(httpx): 페이지네이션(offset), 429 응답 시 재시도(백오프), 초당 5요청 제한 준수
  - 필드 매핑(설정): 이름, 휴대폰, 이메일, 과정 코드, 기수 번호, HRD 상태, 레코드 ID
  - 정규화: 이름은 공백 제거, 휴대폰은 숫자만(`010xxxxxxxx`), 이메일은 소문자
  - 기수 매핑: (과정 코드 → `bootcamps.code`, 기수 번호) → `cohorts`. 실패하면 `students`로 만들지 않고 `roster_sync_runs.unmapped_records`(레코드 ID·이름·Airtable 기수 값)에 남긴다(`unmapped_count` = 목록 길이)
  - **동기화 범위 (ALL / BOOTCAMP / COHORT):** Airtable `filterByFormula`로 과정·기수 필드를 걸어 해당 범위의 레코드만 조회한다.
    - 과정: `{과정필드}='<bootcamps.code>'`
    - 기수: `AND({과정필드}='<code>', {기수필드}=<cohort_number>)`
    - 필드명은 `AIRTABLE_FIELD_MAP`에서 가져온다
    - 값은 수식 문자열로 이스케이프(작은따옴표·역슬래시)해서 넣는다. 사용자 입력이 아니라 DB 값만 쓴다
    - Airtable의 과정 값이 `bootcamps.code`와 다르면, 설정의 과정 값 매핑(`AIRTABLE_BOOTCAMP_VALUE_MAP`)으로 변환한다
  - upsert(`airtable_record_id`): 새 레코드는 `students`(`user_id` NULL, `enrolled_at`은 기수 시작일)로 만들고, 기존 레코드는 `Student.apply_source()`로 Airtable 원천 필드만 갱신한다. 백오피스가 관리하는 `status`·종료일·사유는 덮어쓰지 않는다
  - 같은 레코드의 기수가 Airtable에서 바뀌면 자동으로 옮기지 않고 실패 목록(unmapped_records)에 남겨 운영진이 기수 이동으로 처리한다 (P5에서 확정)
  - **원천 삭제 판정은 이번 범위 안에서만 한다.** 범위에 속하는 기존 명단 중 이번 조회에 없는 것만 `is_removed_in_source=true`로 표시한다(삭제하지 않음). COHORT 동기화가 다른 기수 명단을 건드리면 안 된다.
    - 범위 판정은 저장된 `cohort_id`(BOOTCAMP면 해당 과정의 기수들) 기준이다. `airtable_record_id`가 없는(운영진이 직접 등록한) 수강생은 판정 대상이 아니다
    - 다시 나타난 레코드는 `false`로 되돌린다
  - 이미 가입한(`user_id` 있음) 수강생의 이름·휴대폰이 바뀌면 연결은 유지하고 감사 로그를 남긴다
  - 주기 동기화(taskiq cron 1시간)는 ALL. 수동 실행은 범위를 지정한다
  - 동시 실행 제어(Redis 락):
    - ALL 실행 중에는 다른 모든 동기화를 막는다
    - BOOTCAMP·COHORT는 범위가 겹치는 실행끼리만 막는다(같은 과정). 막히면 409 `roster_sync_in_progress`
  - `roster_sync_runs`에 범위(`scope_type`, `bootcamp_id`, `cohort_id`)와 건수(`fetched`, `upserted`, `removed`, `unmapped`)를 기록한다
  - **가입 대기자 재매칭:** 동기화 후 PENDING 사용자 중 새로 일치하는 명단이 생기면 자동 승인한다 (P7 이후 활성화)
- **API:**
  | 메서드 | 경로 | 권한 |
  | --- | --- | --- |
  | POST | `/api/v1/admin/rosters/sync` | 전체 동기화. `roster.sync` + GLOBAL 범위 (SUPER_ADMIN) |
  | POST | `/api/v1/admin/bootcamps/{id}/rosters/sync` | 과정 동기화. `roster.sync` (해당 과정 범위) |
  | POST | `/api/v1/admin/cohorts/{id}/rosters/sync` | 기수 동기화. `roster.sync` (해당 기수 또는 상위 과정 범위) |
  | GET | `/api/v1/admin/rosters/sync-runs?before=&limit=` | `roster.sync` (담당 범위의 실행만, SUPER_ADMIN은 전체). `next_before` 커서 |
  | GET | `/api/v1/admin/rosters/sync-runs/{id}` | 같은 범위 규칙 (범위 밖이면 404) |
  | GET | `/api/v1/admin/cohorts/{id}/rosters?claimed=&include_removed=` | `roster.sync` (기수의 `students`, 가입 여부·원천 삭제 필터) |
  | GET | `/api/v1/admin/rosters/unmapped` | `roster.sync` + GLOBAL 범위 (SUPER_ADMIN). 최근 실행의 `unmapped_records` |
  - 수동 동기화 요청은 즉시 `roster_sync_runs`(RUNNING)를 만들어 202 + 실행 ID를 돌려주고, 실제 동기화는 taskiq로 처리한다. 상태는 실행 이력 API로 확인한다.
- **테스트:**
  - respx로 여러 페이지·429·필드 누락 응답 고정, 정규화 경계값
  - 멱등: 같은 데이터로 2회 동기화하면 변경 0
  - **범위:** 범위별 `filterByFormula`가 올바르게 만들어지는지(이스케이프 포함). COHORT 동기화 후 다른 기수 명단의 `is_removed_in_source`가 바뀌지 않는지. 기수 매핑 실패 레코드가 `students`에 생기지 않고 실행 이력에 남는지. 재동기화가 백오피스 수강 상태를 덮어쓰지 않는지
  - 동시 실행: ALL과 다른 동기화, 같은 과정의 두 동기화는 409. 서로 다른 과정은 동시 실행 가능
  - 권한: 조교가 담당 기수 외 기수, 또는 ALL을 동기화하면 403

### P6. S3 어댑터 + 교육 인력·계약
- **목표:** 파일 업로드 공통 흐름, 멘토·강사 프로필, 계약 관리.
- PR을 넷으로 나눈다(사용자 결정, 2026-11-09). **P6-1 (구현 기록 26):** S3 어댑터·통합 테스트·CI floci. **P6-2:** educator 모델·마이그레이션. **P6-3:** 계약서 업로드·계약 CRUD·상태 전이 API. **P6-4:** 수동 연결·멘토 프로필 API
- **테이블:** `mentors`, `instructors`, `educator_contracts`, `contract_files`
- **작업:**
  - `integrations/s3.py`(aioboto3, B8): `presign_post(key, content_type, max_bytes)`, `presign_get(key)`, `head(key)`, `delete(key)`. presigned URL은 `S3_PUBLIC_ENDPOINT_URL`로 서명한다 (C7)
  - 업로드 흐름: ① 업로드 요청(서버가 키 `contracts/<uuid7>.<ext>` 발급 + presigned POST) → ② 브라우저가 S3로 직접 업로드 → ③ 확정 요청(서버가 `head`로 크기·타입 확인 후 `contract_files` 생성). 확정되지 않은 객체는 S3 수명 주기 규칙으로 정리한다(운영 버킷 설정)
  - 허용 형식·크기: 계약서 PDF ≤ 10MB, 프로필 이미지 PNG/JPEG/WebP ≤ 2MB
  - 계약 CRUD, 계약 상태 전이(DRAFT → ACTIVE → ENDED / TERMINATED)
  - 운영진이 계약을 가입한 멘토·강사에 **수동 연결**하는 기능 (자동 매칭 실패 시)
  - S3 호환성 시나리오(presigned POST 크기·타입 정책, presigned GET·만료, CORS, 서명 검증, 비공개 버킷, 멀티파트, Range — decisions R7 실측 항목)를 `tests/integration`에 작성하고, CI에 floci 서비스 컨테이너와 버킷 초기화 단계를 추가
- **API:**
  | 메서드 | 경로 | 권한 |
  | --- | --- | --- |
  | POST | `/api/v1/admin/contract-files/uploads` → `.../{key}/confirm` | `contract.manage` |
  | GET/POST/PATCH | `/api/v1/admin/contracts` | `contract.manage` |
  | POST | `/api/v1/admin/contracts/{id}/confirm`, `/terminate` | `contract.manage` (상태 전이, A24. 수정·삭제는 DRAFT만, A25) |
  | GET | `/api/v1/admin/contracts/{id}/file-url` | `contract.manage` (presigned GET) |
  | POST | `/api/v1/admin/contracts/{id}/link` | `contract.manage` (멘토·강사 수동 연결) |
  | GET/PATCH | `/api/v1/me/mentor-profile` | 멘토 본인 (소개, 전문 분야, 프로필 사진 업로드) |
  | DELETE | `/api/v1/admin/contracts/{id}/link` | `contract.manage` (연결 해제, A27) |
  | GET | `/api/v1/admin/mentors` | `contract.manage` (멘토 목록·검색, A28) |
  | GET/PATCH | `/api/v1/admin/mentors/{id}/profile` (+ 사진 업로드·삭제) | `contract.manage` (운영진 대리 수정, A28) |
- **테스트:** floci 통합(인증 강제): 크기 상한 초과·타입 위반 거부, 확정 시 `head` 불일치 거부. 계약 유형과 연결 컬럼 check.

### P7. 수강생·멘토 가입 🔒
- **선행 준비:**
  - **SMS 업체 결정**과 발신번호 등록 (A4). 결정 전까지는 `console` 드라이버로 개발하고, 업체 어댑터는 별도 커밋으로 붙인다
  - Gmail 발송 계정과 DWD 범위(`gmail.send`)
- **목표:** 이메일·SMS 인증을 거친 가입, 자동 승인, 승인 대기 처리, 비밀번호 재설정.
- PR을 다섯으로 나눈다(사용자 결정, A29). **P7-1 (구현 기록 30):** 발송 기반·Gmail 드라이버. **P7-2:** 인증코드·레이트 리밋·가입. **P7-3:** 자동 매칭. **P7-4:** 로그인·잠금·재설정. **P7-5:** 승인 관리
- **가입 흐름:**
  1. **이메일 인증:** `@gmail.com`만 허용한다. 6자리 코드를 발송한다(Redis TTL 10분, 시도 5회, 재발송 간격 60초). 확인되면 가입 토큰 발급(Redis, 30분)
  2. **SMS 인증:** 가입 토큰 + 휴대폰 → 6자리 코드(같은 제한). 이미 다른 계정에 등록된 번호는 거부한다
  3. **가입 완료:** 가입 토큰 + 이름 + 비밀번호 + 유형(수강생 / 멘토) → `users` 생성(argon2, `email_verified_at`, `phone_verified_at`)
  4. **자동 매칭 (A6):**
     - 수강생: `students`에서 (이름, 휴대폰) 일치 + 수강 중 + 원천 존재 + 미가입(`user_id` NULL) (`find_claimable_by_name_and_phone`) → 일치한 등록마다 `Student.claim(user_id)`, `STUDENT` 역할(COHORT 범위) 부여 → APPROVED
     - 멘토: `educator_contracts`에서 (이름, 휴대폰) 일치 + 유형 MENTOR → `mentors` 생성, 계약 `mentor_id` 연결 → APPROVED (MENTOR 역할은 P8 배정에서 부여, A17·A31)
     - 일치 없음 또는 여러 사람과 애매하게 일치하면 PENDING으로 두고 감사 로그를 남긴다
  5. 승인 여부와 관계없이 로그인할 수 있다. PENDING이면 §2.2 게이트로 상태 조회만 가능하다
- **보안:**
  - 레이트 리밋(Redis): IP당·이메일당·휴대폰당 발송 횟수 (예: 휴대폰당 1시간 5회, IP당 1시간 20회)
  - 로그인 실패 5회 시 15분 잠금(이메일 기준)
  - 존재하는 이메일인지 드러내지 않는 응답 (비밀번호 재설정 요청 등)
  - 인증코드는 해시로 저장하고, 비교는 상수 시간으로 한다
- **승인 관리(운영진):** 대기 목록, 승인(수강생은 미가입 `students` 선택, 멘토는 계약 선택 후 연결), 반려(사유 → 감사 로그)
- **API:**
  | 메서드 | 경로 | 설명 / 권한 |
  | --- | --- | --- |
  | POST | `/api/v1/auth/signup/email-code` · `/email-code/verify` | 이메일 인증 |
  | POST | `/api/v1/auth/signup/phone-code` · `/phone-code/verify` | SMS 인증 |
  | POST | `/api/v1/auth/signup` | 가입 완료 + 자동 매칭 |
  | POST | `/api/v1/auth/login` | 이메일+비밀번호 |
  | POST | `/api/v1/auth/password-reset/code` · `/password-reset` | 비밀번호 재설정 |
  | GET | `/api/v1/admin/approvals` | 대기 목록 (`user.approve`, 범위: 수강생은 매니저·조교의 담당 기수, 멘토는 `contract.manage`) |
  | POST | `/api/v1/admin/approvals/{user_id}/approve` · `/reject` | 위와 같음 |
  | GET/POST | `/api/v1/me/member-signup` | 반려 회원의 신청 조회·재신청 (A33) |
- **테스트:**
  - 단위: 매칭 규칙(동명이인, 한 사람이 여러 기수, 원천에서 삭제된 명단, 이미 가입한 등록, 종료된 등록)
  - API: gmail 외 도메인 거부, 코드 만료·시도 초과·재발송 간격, 중복 휴대폰, PENDING 게이트, 레이트 리밋
  - 발송은 메모리 드라이버로 수집해 검증한다

### P8. 기수 멘토링 설정·멘토 배정
- **테이블:** `cohort_mentoring_settings`, `cohort_mentoring_block_times`, `mentoring_holidays`(A34), `cohort_mentors`(A35)
- PR을 둘로 나눈다(사용자 결정). **P8-1 (구현 기록 35):** 설정·금지 시간대·추가 휴일. **P8-2 (구현 기록 36):** 멘토 배정, 멘토 활성화, `mentor.manage`·`staff.assign` 권한과 TEAM_LEAD 역할(A36)
- **규칙 (A35):**
  - ~~배정 기간은 멘토의 ACTIVE 계약 기간 안에 있어야 한다 (M15)~~ → 계약과 배정은 별개(A35)
  - 활성 배정은 (멘토, 기수)당 하나 (부분 유니크, raw SQL, 유형 제거 A41). 시작일은 기수 기간 안, 종료일은 선택
  - 매일 00:00 KST 종료일이 지난 배정을 비활성화(EXPIRED). 삭제 = 비활성화(MANUAL)
  - `pay_unit`은 HOURLY / PER_SESSION만 허용한다
  - 비활성 멘토는 새 배정·재활성화 불가. 멘토 비활성화는 미리보기 후 confirm, 활성 배정을 모두 끈다(MENTOR_DEACTIVATED). 재활성화 응답에 복구 후보, 일괄 재활성화는 가능한 것만(A36)
  - 설정 변경은 진행 중인 신청에 소급하지 않는다
- **API:**
  | 메서드 | 경로 | 설명 |
  | --- | --- | --- |
  | GET/POST | `/api/v1/admin/cohorts/{cohort_id}/mentor-assignments` | 기수 배정 목록(페이징 없음, `include_inactive`)·등록. `mentoring.assignment.manage`(기수 범위) |
  | PATCH/DELETE | `/api/v1/admin/cohorts/{cohort_id}/mentor-assignments/{id}` | 기간·정산 조건 수정 / 비활성화 |
  | POST | `/api/v1/admin/cohorts/{cohort_id}/mentor-assignments/{id}/reactivate` | 배정 재활성화 |
  | POST | `/api/v1/admin/mentors/{id}/deactivate` | `mentor.manage`. `confirm=false`면 함께 꺼질 배정 미리보기, `true`면 실행 |
  | POST | `/api/v1/admin/mentors/{id}/activate` | `mentor.manage`. 응답에 복구 후보 배정 |
  | POST | `/api/v1/admin/mentors/{id}/mentor-assignments/reactivate` | `mentor.manage`. 고른 배정 일괄 재활성화(가능한 것만) |
  | GET | `/api/v1/me/mentor-assignments?include_inactive=` | 멘토 본인 배정(정산 조건 포함) |
- **테스트:** 부분 유니크 위반 409, 시작일 기수 기간 밖 거부, 비활성 멘토 배정 거부, 만료 작업, 멘토 비활성화 미리보기·실행·복구.

### P9. 멘토 일정
- **테이블:** `mentor_unavailable_periods`(일회성·매일·매주 불가 시간), `mentors.accepting_requests`, `cohort_mentoring_settings` 운영시간 컬럼 (A37. `mentor_availabilities`는 두지 않는다)
- PR을 둘로 나눈다(사용자 결정, A37). **P9-1:** 불가 시간 등록·신청 받기 스위치·기수 운영시간(멘토 본인·운영진 대리, 충돌 미리보기 틀). **P9-2:** 신청 가능 시간 계산·조회
- **규칙 (A37):** 불가 시간 외에는 가능, 30분 경계, 자정 넘김 허용(회차 24시간 이하), 불가 시간끼리 겹침 허용, 일회성은 시작 전까지만·반복은 언제든 수정, 신청 받기가 꺼져 있으면 신청 가능 시간 없음, 불가 시간이 늘어나는 변경은 충돌 미리보기 → confirm(실제 처리는 P11)
- **작업:**
  - 멘토 본인·운영진 대리 불가 시간 CRUD, 신청 받기 켜기·끄기, 기수 운영시간 설정
  - **신청 가능 시간 계산 (P9-2):** 기수 운영시간(평일 / 주말·공휴일) − 불가 시간(반복 전개) − 기수 금지 시간대(평일) − 이미 잡힌 세션 − 마감(`min_lead_hours`). 계산은 KST 기준이고 결과는 연속 가능 구간 목록(진행 단위보다 짧은 구간 제외)
  - 조회 범위는 최대 31일, 오늘부터 60일 뒤까지. 활성 배정 기간 안의 날짜만, 수강 중 수강생·운영진·멘토 본인만
- **API:** `/api/v1/me/mentor-schedule`(멘토 본인: 불가 시간·신청 받기), `/api/v1/admin/mentors/{id}/schedule`(운영진 대리, `mentor.manage`), 기수 설정 PUT에 운영시간, `GET /api/v1/mentors/{id}/available-times?cohort_id=&from=&to=`(P9-2)
- **테스트:** 단위로 경계 많이: 자정·월말을 넘는 경우, 반복 전개(매일·매주·반복 종료일), 불가 시간이 부분적으로 겹치는 경우, 금지 시간대, 운영시간 경계, 마감 직전.

### P10. 팀·시간 계좌
- **테이블:** `mentoring_teams`, `mentoring_team_members`, `mentoring_balance_accounts`, `mentoring_balance_transactions`
- PR을 둘로 나눈다(사용자 결정, A39). **P10-1:** 팀 구성(팀·팀원·담당 멘토). **P10-2:** 시간 계좌·원장·지급·조정·조회, 명단 동기화 후 수강 종료 처리(팀에서 빼기·잔여 회수)
- **결정 (A39):** 팀은 팀 멘토링 허용 기수만·담당 멘토 변경 가능·계좌/신청 있으면 삭제 409, 팀원·1:1 대상은 수강 중(가입 무관), 계좌 기간은 첫 지급 때 지정 후 별도 수정, 만료 계좌 지급 거부, 60분 단위·사유 필수, 일괄 대상 4종, Idempotency-Key, 본인 조회는 잔여+원장
- **규칙:**
  - 팀 담당 멘토는 해당 기수의 활성 배정이어야 한다
  - 수강생(수강 등록)은 한 팀에만 소속된다 (유니크, A41)
  - **시간 일괄 지급:** 운영진이 (기수, 대상 1:1 / 팀, 유효기간, 분)을 지정하면 대상 계좌를 만들거나 찾아 STAFF_GRANT를 기록한다. 기본값은 기수 설정의 `default_*_minutes`. 멱등 키(요청 ID)로 중복 지급을 막는다
  - 개별 지급·조정(STAFF_ADJUST ±), 잔여 시간은 음수 불가
  - 원장 기록은 계좌 행을 `SELECT … FOR UPDATE`로 잠그고 같은 트랜잭션에서 한다
- **API:** 팀 CRUD·팀원 관리(`mentoring.team.manage`), 일괄·개별 지급(`mentoring.balance.grant`), 원장 조회(운영진 / 본인 `GET /api/v1/me/balances`)
- **테스트:** 동시 지급·차감 경합(통합 테스트에서 동시 트랜잭션 2개), 음수 방지, 멱등 지급.

### P11. 신청·승인·반려·취소
- **유형 제거 선행 PR (A41):** 배정·팀·계좌에서 멘토링 유형(평시/프로젝트)을 뺀다(마이그레이션 16)
- PR을 셋으로 나눈다(사용자 결정, A42). **P11-1:** 신청(검증·시간 보류)·조회·승인 전 취소·대기 만료 작업. **P11-2:** 승인·반려·세션 생성. **P11-3:** 승인 후 취소·운영진 취소·변경, 연동(불가 시간 충돌 처리, 멘토 변화 시 대기 신청 취소, 수강 종료 시 대기 신청·1:1 세션 취소, 신청 가능 시간에서 세션 제외). P11-3은 다시 둘로 나눈다(A44): **P11-3a** 승인 후 취소·운영진 취소·변경 + 세션 제외, **P11-3b** 연동
- **결정 (A42):** 신청 시간은 진행 단위 배수·최대 120분, 희망 일시는 각각 신청 가능 구간 안·서로 겹침 금지, 대기 건수는 1:1 수강생당·팀 팀당, 팀은 누구나 신청·취소는 신청자만·조회는 팀원 모두, 주제 100자·상세 필수 2,000자, 승인은 시작 전까지, 반려·취소 사유 필수, 운영진은 조회·취소(환불 선택)만, 세션 제목 자동
- **테이블:** `mentoring_requests`, `mentoring_sessions` (Meet 필드는 P12에서 채움)
- **상태 전이와 원장:**
  | 동작 | 주체 | 조건 | 신청 상태 | 원장 | 세션 |
  | --- | --- | --- | --- | --- | --- |
  | 신청 | 수강생(팀 신청은 팀원) | 희망 일시 1~3이 가능 시간 안, `allowed_duration`의 배수, 대기 신청 수 < `max_pending_requests`, 계좌 유효기간 안 | PENDING | HOLD | — |
  | 승인 | 담당 멘토 | 희망 일시 중 하나 선택, 아직 가능, 겹침 없음 | APPROVED | USING | SCHEDULED 생성 |
  | 반려 | 담당 멘토 | PENDING | REJECTED (사유) | RELEASE | — |
  | 취소(승인 전) | 신청자 | PENDING | CANCELED | RELEASE | — |
  | 취소(승인 후) | 수강생·멘토 | 시작 `min_lead_hours` 전 | CANCELED | REFUND | CANCELED |
  | 취소(마감 후) | 운영진 | 환불 여부 선택 | CANCELED | REFUND 또는 없음 | CANCELED |
  | 변경 | 신청자 | 취소 + 새 신청(`replaced_request_id`) | — | — | — |
- **동시성:** 승인 시 계좌 잠금 → 세션 INSERT(EXCLUDE로 멘토 일정 겹침 차단, 위반 시 409 `mentor_schedule_conflict`). 원장은 `(request_id, type)` 유니크로 같은 처리가 두 번 기록되지 않게 막는다.
- **API:** `POST /api/v1/mentoring/requests`, `GET /api/v1/me/mentoring/requests`, `POST .../{id}/approve|reject|cancel`, 운영진 `GET /api/v1/admin/cohorts/{id}/mentoring/requests`, `POST /api/v1/admin/mentoring/requests/{id}/cancel`(`mentoring.request.cancel`, `refund: bool`)
- **테스트:** 상태 전이표 전 항목, 동시 승인 경합, 마감 경계, 팀 신청 권한.

### P12. Google Meet 연동 🔒
- **선행 준비:**
  - Workspace 관리자: 서비스 계정 DWD 범위 등록(`gmail.send`, `meetings.space.created`, `meetings.space.readonly`). Drive는 위임 대신 주최 계정의 `Meet Recordings` 폴더를 서비스 계정에 공유(P13 전, A47)
  - GCP 프로젝트: Pub/Sub 토픽, **pull 구독**, Workspace Events가 토픽에 발행할 권한
- **작업:**
  - 승인 커밋 후(`uow.on_commit`) taskiq로 Meet Space 생성을 enqueue한다. 실패하면 백오프 재시도하고, 성공하면 `google_space_name` / `google_meet_url`을 저장한다
  - Space별 Workspace Events 구독을 만든다(회의 시작·종료, 녹화·전사 생성)
  - Pub/Sub pull 작업(30초): 메시지 → 이벤트 처리 → ack. 이벤트 ID로 멱등 처리한다
    - 회의 시작 → `IN_PROGRESS`, `actual_started_at`, `google_conference_record_name`
    - 회의 종료 → `actual_ended_at`
    - 녹화·전사 생성 → `recording_status` 갱신, `mentoring_artifacts` PENDING 생성 (P13에서 수집)
  - 구독 만료 전 갱신 작업
- **API:** 세션 응답에 Meet URL 포함 (해당 수강생·멘토·운영진만)
- **테스트:** 가짜 `MeetClient` / `EventSubscriber`로 이벤트 순서 뒤바뀜·중복 수신 시 멱등, Space 생성 실패 후 재시도.

### P13. 기록·내부 메모·녹화 수집·중계
- **테이블:** `mentoring_session_notes`, `mentoring_artifacts`
- **작업:**
  - **기록 제출(멘토, M27):** 종료 후 COMPLETED(`record_duration_minutes`, 주제, 요약) 또는 NO_SHOW. **NO_SHOW면 REFUND** (M28). 제출 후 수정은 정산 마감 전까지만 가능하다
  - 내부 메모: 세션당 1개, 멘토 본인과 운영진만. 작성·수정은 감사 로그에 남긴다
  - 녹화 수집: Drive API로 파일 메타 조회 → `mentoring_artifacts` COMPLETED. 보완 폴링 작업(1시간, 종료 7일 이내)
  - **스트리밍 중계:** `GET /api/v1/mentoring/sessions/{id}/artifacts/{artifact_id}/content` — 권한 확인 후 Drive에서 `Range` 요청을 그대로 넘겨 `StreamingResponse`로 전달한다(206, `Content-Range`). 메모리에 파일 전체를 올리지 않는다
- **API:** 기록 제출·수정, 메모 조회·저장, 아티팩트 목록·스트리밍, 운영진용 기록 미제출 세션 목록
- **테스트:** 기록 상태 전이, NO_SHOW 환불, 권한별 메모 노출, Range 응답(respx로 Drive 고정).

### P14. 정산
- **테이블:** `mentoring_settlements`, `mentoring_settlement_items`
- **작업:**
  - 집계(멘토 × 월, DRAFT): 해당 월(KST)에 시작한 COMPLETED / NO_SHOW 세션 중 아직 정산되지 않은 세션
    - SESSION: 정산 기준 시간 = `cost_settlement_policy`가 STUDENT_REQUEST면 신청 시간, ACTUAL_DURATION이면 `record_duration_minutes`. 금액은 HOURLY면 `floor(단가 × 분 / 60)`, PER_SESSION이면 단가
    - NO_SHOW: 금액 = 배정의 `no_show_pay_amount`
    - 단가는 세션 시작일에 유효한 `cohort_mentors` 배정에서 가져와 스냅샷한다
  - 다시 집계하면 DRAFT를 새로 계산한다. 마감(CLOSED)하면 바꿀 수 없다. 마감 이후의 기록 수정은 막는다
  - 기록 미제출 세션이 있으면 마감 전에 경고한다(목록 반환)
- **API (`mentoring.settlement.close`):** 집계 실행, 조회, 마감, CSV 내보내기 / 멘토 본인: `GET /api/v1/me/settlements`
- **테스트:** 금액 계산 경계(내림), 정책별 분 계산, 세션 중복 정산 방지(유니크), 마감 후 수정 거부.

### P15. 채팅
- **선행 결정:** 실시간 전송 방식(WebSocket / SSE, B7)
- **테이블:** `mentoring_chat_threads`, `mentoring_chat_messages`, `mentoring_chat_reads`
- **작업:**
  - 1:1(수강생-멘토, 해당 기수 배정 관계일 때만) / 팀(팀원 + 담당 멘토) 채팅방
  - 메시지 저장 후 Redis Pub/Sub으로 실시간 전달
  - 목록은 커서 기반이다. 안 읽은 수는 `last_read_at` 이후 메시지 수로 계산한다
- **테스트:** 참여자 아닌 사용자 403, 커서 페이지네이션, 읽음 갱신.

---

## 5. 선행 준비물 체크리스트 (외부)

설정 방법은 `docs/operations/external_setup.md`, 운영 배포 설정은 `docs/operations/production_notes.md`에 정리했다.

| 준비물 | 필요한 PR | 담당 | 상태 |
| --- | --- | --- | --- |
| Airtable PAT·베이스·테이블 ID, 필드 구조 | P5 | 사용자 | 확인 완료 (2026-11-09) |
| **SMS 발송 업체 결정**, 발신번호 등록 | P7 | 사용자 | 미정 |
| Gmail 발송 계정, 서비스 계정 DWD `gmail.send` | P7 | Workspace 관리자 | 진행 중 (키 유효, 위임 `unauthorized_client`) |
| 서비스 계정 DWD Meet·Drive 범위 | P12, P13 | Workspace 관리자 | 미확인 |
| GCP 프로젝트, Pub/Sub 토픽·pull 구독, Workspace Events 발행 권한 | P12 | 사용자 | 미확인 |
| AWS S3 운영 버킷, IAM 역할, 수명 주기 규칙(미확정 업로드 정리) | P6 (운영 배포 시) | 사용자 | 미확인 |
| 최초 SUPER_ADMIN 계정 지정 | P3 | 사용자 | — |

## 6. 리스크

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| SMS 업체 미정 | P7 운영 투입 지연 | 인터페이스 + console 드라이버로 먼저 개발, 업체 결정 후 어댑터만 추가 |
| Airtable 구조 변경 | 동기화 실패, 매칭 누락 | 필드 매핑을 설정으로, 필드 누락 시 실행 실패로 기록하고 기존 명단 유지 |
| 이름·휴대폰 매칭 실패(오타, 번호 변경) | 승인 대기 증가 | 운영진 수동 승인 화면, 동기화 후 대기자 재매칭 |
| Workspace Events 구독 만료·이벤트 유실 | 진행 상태·녹화 누락 | 구독 갱신 작업, 녹화 보완 폴링, 진행 상태는 기록 제출로 최종 확정(M27) |
| 젊은 에뮬레이터(floci) | 로컬·CI 결과와 운영 차이 | 호환성 테스트 유지, 운영 배포 전 실제 S3 스모크 테스트 |
| 원장 동시성 | 잔여 시간 오차 | 계좌 행 잠금, 원장 유니크, 동시성 통합 테스트 |

## 7. 진행 체크리스트

- [x] P1 마스터 데이터 모델과 첫 마이그레이션
  - [x] P1-1 identity·audit 모델과 첫 마이그레이션 (구현 기록 03)
  - [x] P1-2 academy 모델 (구현 기록 05)
  - [x] P1-3 organization 모델 (구현 기록 06)
- [x] P2 인증 기반과 운영진 로그인
  - [x] P2-1 인증 기반과 Google 로그인 (구현 기록 08)
  - [x] P2-2 운영진 최초 정보 입력 (구현 기록 09)
- [x] P3 권한
  - [x] P3-1 역할·권한 모델, 역할 시드, 최고 관리자 CLI (구현 기록 10)
  - [x] P3-2a 권한 판정과 require_permission 의존성 (구현 기록 13)
  - [x] P3-2b 운영진 가입 승인·반려 (구현 기록 14)
  - [x] P3-3a 과정·기수 담당자 관리 API (구현 기록 15)
  - [x] P3-3b 회원 역할 관리 API (구현 기록 16)
- [x] P4 조직·과정·기수 관리 API
  - [x] P4-1 조직(부서·직위·직원) 관리 API (구현 기록 17)
  - [x] P4-2 학사(HRD 과정·회차, 운영과정, 기수) 관리 API (구현 기록 18)
- [x] P5 Airtable 수강생 명단 동기화
  - [x] P5-1 과정 별칭 컬럼과 Airtable 클라이언트 (구현 기록 19)
  - [x] P5-2a 레코드 해석·상태 매핑·동기화 서비스 (구현 기록 20)
  - [x] P5-2b 동시 실행 락·taskiq 작업 (구현 기록 21)
  - [x] P5-2c 명단 동기화 관리 API (구현 기록 22)
  - [x] P5-3 과정-기수 테이블로 학사 마스터 동기화 (구현 기록 23)
  - [x] P5-4 수강생 테이블 실구조 확인과 레코드 링크 매핑 (구현 기록 25)
- [x] P6 S3 어댑터 + 교육 인력·계약
  - [x] P6-1 S3 어댑터와 S3 시나리오 통합 테스트·CI floci (구현 기록 26)
  - [x] P6-2 educator 모델·마이그레이션 (구현 기록 27, A22·A23)
  - [x] P6-3 계약서 업로드·계약 CRUD·상태 전이 API (구현 기록 28, A24·A25·A26)
  - [x] P6-4 계약 수동 연결·멘토 프로필 API (구현 기록 29, A27·A28)
- [x] P7 수강생·멘토 가입
  - [x] P7-1 메일·SMS 발송 기반과 Gmail 드라이버 (구현 기록 30, A29·B13)
  - [x] P7-2 인증코드·레이트 리밋·가입 (구현 기록 31, A30·B14)
  - [x] P7-3 자동 매칭 (수강생·멘토) (구현 기록 32, A31)
  - [x] P7-4 로그인·잠금·비밀번호 재설정 (구현 기록 33, A32)
  - [x] P7-5 운영진 승인 관리 (구현 기록 34, A33)
- [x] P8 기수 멘토링 설정·멘토 배정
  - [x] P8-1 기수 멘토링 설정·금지 시간대·추가 휴일 (구현 기록 35, A34·B15)
  - [x] P8-2 멘토 배정·멘토 활성화·팀리드 권한 (구현 기록 36, A35·A36)
- [x] P9 멘토 일정
  - [x] P9-1 불가 시간 등록·신청 받기·기수 운영시간 (구현 기록 37, A37)
  - [x] P9-2 신청 가능 시간 계산·조회 (구현 기록 38, A38)
- [x] P10 팀·시간 계좌
  - [x] P10-1 팀 구성 (구현 기록 39, A39)
  - [x] P10-2a 시간 계좌·원장·지급·조정·기간 수정·조회 (구현 기록 40, A40)
  - [x] P10-2b 명단 동기화 후 수강 종료 처리(팀에서 빼기·잔여 회수) (구현 기록 41, A39)
- [x] P11 신청·승인·반려·취소
  - [x] 멘토링 유형 제거 (구현 기록 42, A41)
  - [x] P11-1 신청·시간 보류·조회·승인 전 취소·대기 만료 (구현 기록 43, A42)
  - [x] P11-2 승인·반려·세션 생성 (구현 기록 44, A43)
  - [x] P11-3a 승인 후 취소·운영진 취소·변경·신청 가능 시간에서 세션 제외 (구현 기록 45, A44)
  - [x] P11-3b 불가 시간 충돌·멘토 변화·수강 종료 연동 (구현 기록 46, A45)
- [ ] P12 Google Meet 연동
- [ ] P13 기록·내부 메모·녹화 수집·중계
- [ ] P14 정산
- [ ] P15 채팅
