# `database_schema.dbml` 초안 리뷰

> **상태 (2026-11-05): 이력 보존용.** 최초 초안(`database_schema.dbml`)에 대한 리뷰다. 이후 `database_schema_v2.dbml`이 멘토링 범위로 축소·재설계됐고, 여기서 제안한 테이블 다수(exam, ucansign, 출결, 공통 files 등)는 현재 스키마에 없다. 작업 기준은 `database_schema_v2.dbml`과 `docs/decisions.md`다.

대상: `docs/database_schema.dbml` (초안)
참고: `docs/analysis/*.md` (기존 5개 서비스 분석), `docs/analysis/00_integration_requirements.md`

## 0. 총평

- 조직(부서·직원), 회원, HRD-Net 과정·회차, 부트캠프·기수·과목, 과제·프로젝트로 이어지는 **학사 운영 코어는 구조가 잘 잡혀 있다.**
- 다만 지금 초안은 **신규 학사 기능 중심**이다. 통합 대상인 기존 5개 서비스(Auto_monitor, exam, mentor, ucansign, vacation)의 테이블은 거의 없다.
  - 특히 멘토링은 초안이 "팀 단위 멘토링 일지" 모델이다. 기존 mentor 서비스는 **1:1 슬롯 예약 → 승인 → Calendar/Meet → 기록·정산** 모델이라 구조가 다르다(§4.3).
- 권한(RBAC), 파일, 감사 로그, 발송 아웃박스, 외부 자격증명, 공휴일 같은 **공통 테이블이 빠져 있다**(§3).
- 명백한 오타와 타입 오류가 몇 군데 있다(§1).

우선순위: **§1 오류 수정 → §2 기존 테이블 수정 → §3 공통 테이블 → §4 서비스별 테이블**

---

## 1. 즉시 수정 (문법·타입 오류)

| 위치 | 현재 | 문제 | 수정안 |
| --- | --- | --- | --- |
| L11 `departments.description` | `text(500)` | PostgreSQL `text`에는 길이 지정이 없다 | `varchar(500)` |
| L148 `weekend_se` | `default: 9` | enum 값이 아님 | `default: 'WEEKDAY'` 등 또는 nullable |
| L149 `day_night_se` | `DayNigthSeType`, `default: False` | 타입명 오타, enum에 bool 기본값 | `DayNightSeType`, `default: 'DAY'` |
| L127-129 `educator_contracts` check | `mentor_id`, `instructor_id` 참조 | **해당 컬럼이 테이블에 없다**. 조건식도 둘 다 NULL이면 통과한다 | 두 컬럼 추가 + `num_nonnulls(mentor_id, instructor_id) = 1` |
| L408 `uploaded_at` | `timestampz` | 오타 | `timestamptz` |
| L423-424 `level_based_classes` | `start_date uuid`, `end_date uuid` | 날짜 컬럼이 uuid | `date` |
| L534 `project_team_members.student_id` | `uuiid` | 오타 | `uuid` |
| L66 `employees.slack_user_id` | `bigint` | Slack user ID는 `U01ABCDEF` 같은 **문자열** | `varchar(20)` |
| L151-152 `total_train_fee`, `train_fee_per_hour` | `smallint` | 최대 32,767이라 훈련비(수백만 원)가 들어가지 않는다 | `integer`(원 단위). 금액 계산이 있으면 `numeric(12,0)` |
| enum 미정의 | `EducatorType`, `StudentStatus`, `ScheduleType`, `RecordingUploadStatus`, `ProjectMemberStatus` | 참조하지만 정의가 없다 | Enum 블록 추가 |
| enum 미사용 | `InstructorType` | 정의했지만 쓰는 곳이 없다 | `cohort_subjects` 등의 강사 배정에 사용(§2.6) |
| `oauth_accounts` | PK 없음 | 식별·중복 방지 불가 | `id` PK + `unique(provider, oauth_provider_id)` + `unique(user_id, provider)` |

---

## 2. 기존 테이블 수정 제안

### 2.1 공통 컨벤션
- **uuid7**: PostgreSQL 18이면 `uuidv7()`을 DB 기본값으로 쓸 수 있다. 그보다 낮은 버전이면 애플리케이션에서 생성한다(Tortoise 모델 `default=uuid7`). 사용할 PostgreSQL 버전을 명시해 두자.
- **`updated_at`**: nullable보다 `not null default now()` + 애플리케이션 `auto_now`가 정렬·동기화 쿼리에서 다루기 쉽다.
- **soft delete**: 탈퇴 회원, 삭제된 시험(exam `deleted_at`), 보관된 기수(exam `archived_at`)처럼 이력을 보존해야 하는 테이블에는 `deleted_at` / `archived_at`이 필요하다.
- **외부 숫자 ID**(Discord snowflake, UCanSign 19자리 ID): `bigint`에는 저장할 수 있다. 다만 JS 정밀도를 넘으므로 **API 응답에서는 반드시 문자열로 직렬화**한다. 단순하게 가려면 `varchar(32)`로 저장한다.
- **중복 정의 제거**: 첨부파일 테이블이 5개(`assignment_attachments`, `assignment_submission_attachments`, `level_based_*_attachments` 2개, `mentoring_recordings`)이고, 계약서·이력서·PPT의 `s3_key`도 따로 있다. 공통 `files` 테이블로 통합한다(§3.2).

### 2.2 `departments`
- `parent_id`가 `not null`이면 **최상위 부서를 만들 수 없다** → nullable.
- `name`: 같은 부모 아래에서 유일해야 한다 → `unique(parent_id, name)`.
- exam의 `organizations`(UI상 "팀"), mentor의 "교육팀별 시트 탭"이 사실상 부서 단위다. 그래서 **부서가 데이터 소유 범위(테넌트)가 될지** 정해야 한다. 그렇다면 시험·문제은행 같은 데이터에 `department_id`가 붙는다.

### 2.3 `users`
| 컬럼 | 문제 | 제안 |
| --- | --- | --- |
| `hashed_password` | Google OAuth 전용 계정(사내 도메인)은 비밀번호가 없다 | nullable + `check(hashed_password is not null or exists oauth)`는 앱 레벨에서 검증 |
| `email` | 대소문자가 다른 중복 가입 | `citext` 또는 `unique(lower(email))` |
| `name varchar(10)` | 외국인·영문 이름에는 짧다 | `varchar(50)` |
| `phone_number`, `birth_date` | 직원·멘토에게는 필수가 아닐 수 있다. 민감 정보다 | 역할별 필수 여부 재검토. 암호화 또는 접근 로그. 전화번호 검색이 필요하면(exam 본인 확인은 뒷4자리) 해시·뒷4자리 생성 컬럼 |
| `is_admin` | 역할이 여러 가지라 bool 하나로는 부족하다 | RBAC 테이블로 대체(§3.1) |
| (없음) | 탈퇴·비활성 사유 | `deleted_at`, `deactivated_reason` |
| (없음) | ucansign 서류에 주소가 필요하다 | 수강생 프로필(`students` 또는 `student_profiles`)에 `address` |

### 2.4 `employees` / `bootcamp_staffs` / `cohort_staffs`
- `bootcamp_staffs`, `cohort_staffs`에 **담당 역할 구분이 없다.**
  - Auto_monitor는 기수별 `managers`(운영 매니저)와 `assistants`(조교)를 구분하고, 알림 멘션 대상도 다르다.
  - `role StaffRole` (`MANAGER`, `ASSISTANT`, `OPERATOR` 등) 컬럼을 추가하고 unique를 `(employee_id, cohort_id, role)`로 바꾼다.
- `slack_user_id`: §1의 타입 수정에 더해, **Slack 워크스페이스가 여럿이면** `(team_id, user_id)` 쌍이 필요하다.
- 조교·멘토 중에 직원(`employees`)이 아닌 외부인이 있다면 `cohort_staffs.employee_id` 대신 `user_id`를 참조해야 할 수 있다(확인 필요).

### 2.5 HRD-Net / `bootcamps` / `cohorts`
- `hrd_net_bootcamps.hrd_net_id`: unique 추가.
- `hrd_net_bootcamp_cohorts`
  - `unique(hrd_net_bootcamp_id, cohort_num)`.
  - **HRD-Net 등록 훈련 시작일·종료일, 훈련과정 코드, 자비부담 총액**: ucansign의 `camp_profiles`(환불 계산, 서류 값)가 쓰는 정보다. 이 테이블로 옮기는 것이 자연스럽다.
- `bootcamps.hrd_net_bootcamp_id`(1:1)
  - HRD-Net 과정은 연도나 재승인 때마다 새 ID로 다시 등록되는 경우가 많다. **운영 과정 1개 : HRD 과정 N개**가 될 수 있다(확인 필요).
  - 실제 매핑은 이미 `cohorts.hrd_net_cohort_id`가 하고 있다. 그렇다면 `bootcamps`의 FK는 빼는 편이 낫다.
- `cohorts`
  - `bootcamp_id`와 `hrd_net_cohort_id → hrd_net_bootcamp`가 **서로 다른 과정을 가리킬 수 있다**. 앱 레벨 검증 규칙을 명시하자.
  - `parent_id unique` + `is_derived`: `is_derived = (parent_id is not null)`이면 중복 컬럼이다. 의미가 다르다면 note에 정의해 두자. 파생 기수가 1개보다 많을 수 있다면 `unique`를 빼야 한다.
  - **상태 컬럼**이 필요하다: `status` (`PLANNED` / `ONGOING` / `ENDED` / `ARCHIVED`). exam은 보관 기수를 목록에서 숨긴다.
  - `cohort_number int` ↔ `hrd_net_bootcamp_cohorts.cohort_num smallint`: 타입·이름 통일.
  - **수업 시간표**가 없다. Auto_monitor는 기수별 요일·수업 시작/종료·휴식 시간으로 감시 구간을 정한다. `cohort_schedules`는 일회성 일정이라 반복 시간표와 따로 두는 것을 권장한다(§4.1 `cohort_class_hours`).
  - **캠프명 별칭**: vacation은 같은 캠프를 선택값, 시트 라벨, HRD 공식명 세 형태로 쓴다. 이관 매칭용으로 `bootcamp_aliases(bootcamp_id, alias, source)`를 두면 편하다.

### 2.6 `subjects` / `chapters` / `cohort_subjects`
- `subjects`가 `chapter_id`와 `bootcamp_id`를 함께 가진다. 그런데 `chapters`에도 `bootcamp_id`가 있어 **값이 어긋날 수 있다**. `bootcamp_id`를 빼거나 복합 FK로 묶는다.
- `subjects.version`: 같은 행에서 숫자만 올리면 **이전 버전 내용이 사라진다**. 이미 운영된 기수가 어떤 버전의 과목을 들었는지 추적하려면 다음 둘 중 하나가 필요하다.
  - `unique(bootcamp_id, code, version)`으로 버전마다 새 행을 만든다.
  - `subject_versions` 테이블을 분리하고, `cohort_subjects`가 특정 버전을 참조한다.
- `subjects`에 챕터 내 순서(`ordering`)가 없다.
- `cohort_subjects.instructor_id not null`: 과목당 강사가 1명으로 고정된다. 주강사와 보조강사가 있거나 강사가 바뀌면 `cohort_subject_instructors(cohort_subject_id, instructor_id, role InstructorType, start_date, end_date)`로 분리한다. 미사용 enum `InstructorType`을 여기서 쓴다.

### 2.7 `cohort_schedules`
- `schedule_type`이 종일(ALL_DAY)이면 시간이 없다 → `start_time`/`end_time` nullable + `check(schedule_type = 'ALL_DAY' or (start_time is not null and end_time is not null))`.
- 공휴일은 기수 일정이 아닌 **전역 `holidays` 테이블**로 둔다(§3.5).

### 2.8 과제 (`assignments` ~ `assignment_submissions`)
- `assignment_deployments.assignment_id not null`: note에는 "신규 정의 가능"이라고 되어 있다 → nullable.
- `assignment_attachments`가 `assignments`(템플릿)만 참조한다. 그래서 **배포본에 첨부를 따로 붙이거나 바꿀 수 없다**. note에는 "기수-과목별"이라고 되어 있어 의도와 FK가 어긋난다. 배포본 기준으로 첨부를 연결하자.
- `assignment_deployments`에 **공개일·마감일**(`opens_at`, `due_at`), 지각 제출 허용 여부가 없다.
- `assignment_submissions`에 없는 것들
  - 중복·재제출 규칙: `unique(deployment_id, submitter_id)` 또는 `attempt_no`
  - `submitted_at`, `status`(제출/지각/반려)
  - 채점·피드백(`score`, `feedback`, `graded_by`, `graded_at`)
- **수준별 수업 과제 4개 테이블은 일반 과제 테이블과 구조가 같다.** 배포 대상을 일반화하면 테이블 8개가 4개로 줄어든다.
  - `assignment_deployments.cohort_subject_id`(nullable) + `level_based_class_id`(nullable) + `check(num_nonnulls(...) = 1)`
  - 이렇게 하면 `level_based_class_assignments*` 테이블들을 제거할 수 있다.

### 2.9 수준별 수업
- `level_based_class_students.student_id unique`: 한 수강생이 **평생 하나의 수준별 반에만** 들어갈 수 있게 된다 → `unique(class_id, student_id)`.
- `level_based_classes`에 반 이름, 레벨, 대상 과목이 없다.

### 2.10 `students`
- `user_id unique` + `cohort_id`: 한 사람은 **하나의 기수에만** 등록될 수 있다. 중도포기 후 재수강이나 다른 과정 수강이 불가능하다.
  - `unique(user_id, cohort_id)`로 바꿔서 이 테이블을 "수강 등록(enrollment)"으로 본다.
  - 사람 단위 정보(주소 등)는 `users`나 별도 `student_profiles`로 둔다.
- `hrd_net_status`만으로는 운영 상태를 표현하기 어렵다. 운영 상태(`ENROLLED` / `COMPLETED` / `DROPPED` / `EARLY_EMPLOYED` …)와 `enrolled_at`, `dropped_at`을 둔다. `StudentStatus` 정의도 필요하다.
- `discord_id bigint not null`
  - 디스코드 미연동 수강생이 있다 → nullable.
  - `employees.discord_user_id`와 이름을 통일한다.
  - **기수(길드) 안에서 유일**해야 한다. Auto_monitor 규칙이다.
- Auto_monitor가 쓰는 **ZEP 닉네임**(기수 내 유일, 바뀔 수 있음)이 없다. 외부 계정 식별자는 `student_external_accounts`로 분리하는 것을 권장한다(§3.6).

### 2.11 멘토 / 강사 / 계약
- `mentors`에 프로필(소개, 전문 분야, 사진 파일)과 **담당 기수**가 없다.
  - 기존 mentor는 `mentorCohorts[]`로 담당 기수를 관리하고, 사진은 Firestore에 base64로 저장했다.
  - `mentor_cohorts(mentor_id, cohort_id)` + `profile_image_file_id`를 추가한다.
- `instructors.resume_url`은 `files` 참조로 바꾼다.
- `educator_contracts`
  - §1의 컬럼 누락을 고친다.
  - 계약 기간(`start_date`, `end_date`), 단가(시급·회당), 상태, 서명 여부를 추가한다. 단가는 mentor **정산**의 근거가 된다.
  - `managed_staff_id`보다 `manager_employee_id`가 의미를 더 잘 드러낸다.

### 2.12 프로젝트
- `project_teams`가 `projects`의 `title`/`goal`/`body`/`notion_url`을 그대로 복제하고 있다. 의도된 것이라면(팀별 주제) 괜찮지만, note가 "프로젝트 제목"으로 같아서 헷갈린다. 팀명은 `team_name`으로 하는 등 이름을 구분한다.
- `ppt_s3_key`(projects) ↔ `ppt_url`(teams) 불일치 → `files` 참조로 통일한다.
- `project_team_members`
  - `unique(project_team_id, student_id)`.
  - "한 프로젝트에서 한 팀에만 소속"을 보장하려면 `project_id`를 비정규화해서 `unique(project_id, student_id)`.
- 프로젝트 멘토링: `mentoring_teams`에 `project_team_id`(nullable)를 두면 PROJECT_MENTORING과 연결된다.

---

## 3. 추가가 필요한 공통 테이블

### 3.1 권한 (RBAC + 범위)
`users.is_admin` 하나로는 기존 서비스의 권한 구분을 담을 수 없다.
- Auto_monitor: admin / manager / assistant
- exam: owner / admin / author / grader. **grader는 author의 부분집합이 아니다**
- mentor: superAdmin / operator / mentor / student
- 미리보기 계정(읽기 전용 대리 로그인)

```dbml
Table roles {
  id uuid [pk]
  code varchar(50) [not null, unique, note: "SUPER_ADMIN, COHORT_MANAGER, EXAM_AUTHOR, EXAM_GRADER ..."]
  name varchar(50) [not null]
  description text [null]
}

Table permissions {
  id uuid [pk]
  code varchar(100) [not null, unique, note: "exam.question.write, mentoring.settlement.close ..."]
  description text [null]
}

Table role_permissions {
  role_id uuid [ref: > roles.id]
  permission_id uuid [ref: > permissions.id]
  indexes { (role_id, permission_id) [pk] }
}

Table user_roles {
  id uuid [pk]
  user_id uuid [not null, ref: > users.id]
  role_id uuid [not null, ref: > roles.id]
  scope_type ScopeType [not null, note: "GLOBAL, DEPARTMENT, BOOTCAMP, COHORT"]
  scope_id uuid [null, note: "scope_type=GLOBAL이면 null"]
  granted_by uuid [null, ref: > users.id]
  created_at timestamptz [not null, default: `now()`]
  indexes { (user_id, role_id, scope_type, scope_id) [unique] }
}
```

`bootcamp_staffs`·`cohort_staffs`를 유지할지, `user_roles`(scope=BOOTCAMP/COHORT)로 흡수할지 정해야 한다. 둘 다 두면 이중 관리가 되므로 **하나로 통일하는 것을 권장**한다. 담당자 목록 표시와 알림 멘션에는 staffs 테이블이 편하다.

### 3.2 파일
```dbml
Table files {
  id uuid [pk]
  storage StorageType [not null, note: "S3, GOOGLE_DRIVE (기존 Drive 파일 이관 전 참조용)"]
  bucket varchar(100) [null]
  object_key varchar(1024) [not null, note: "S3 key 또는 Drive file id"]
  original_name varchar(255) [not null]
  content_type varchar(100) [not null]
  size_bytes bigint [not null]
  checksum_sha256 char(64) [null, note: "vacation PDF 중복 방지 등"]
  status FileStatus [not null, default: 'PENDING', note: "PENDING, UPLOADED, FAILED, DELETED"]
  is_sensitive bool [not null, default: false, note: "서명·생년월일 포함 PDF 등 → presigned URL만 허용"]
  uploaded_by uuid [null, ref: > users.id]
  created_at timestamptz [not null, default: `now()`]
  indexes { (storage, bucket, object_key) [unique] }
}
```
각 첨부 테이블은 `(owner_id, file_id, ordering)` 형태의 연결 테이블로 바꾼다. 연결 대상이 많으면 `file_links(file_id, owner_type, owner_id)` 하나로 묶을 수도 있다(이 경우 FK 무결성을 포기한다). `mentoring_recordings`의 업로드 상태도 `files.status`로 흡수할 수 있다.

### 3.3 감사 로그
```dbml
Table audit_logs {
  id uuid [pk]
  actor_user_id uuid [null, ref: > users.id, note: "시스템 작업이면 null"]
  action varchar(100) [not null, note: "cohort.settings.update, exam.publish ..."]
  target_type varchar(50) [not null]
  target_id uuid [null]
  before jsonb [null]
  after jsonb [null]
  ip inet [null]
  created_at timestamptz [not null, default: `now()`]
  indexes { (target_type, target_id, created_at) }
}
```
흡수 대상: Auto_monitor `changes`, mentor `auditLogs`, ucansign 위험 작업 기록.

### 3.4 발송 아웃박스 (중복 발송 방지 공통)
Auto_monitor·ucansign·mentor가 모두 쓰는 `pending → sending → sent | failed | uncertain | cancelled` 패턴이다.
```dbml
Table outbound_messages {
  id uuid [pk]
  channel OutboundChannel [not null, note: "SLACK, DISCORD, EMAIL, GOOGLE_CALENDAR, GOOGLE_SHEETS ..."]
  dedup_key varchar(128) [not null, unique, note: "결정적 해시. 메일 1회 발송 키 등"]
  source_type varchar(50) [not null, note: "monitor.alert, mentoring.booking ..."]
  source_id uuid [null]
  destination varchar(255) [not null, note: "채널 ID, 이메일 등"]
  payload jsonb [not null]
  status OutboundStatus [not null, default: 'PENDING']
  attempt_count smallint [not null, default: 0]
  manual_resend_count smallint [not null, default: 0, note: "uncertain 수동 재발송 (Auto_monitor 최대 3)"]
  next_attempt_at timestamptz [null]
  claimed_by varchar(100) [null]
  lease_expires_at timestamptz [null]
  provider_message_id varchar(255) [null, note: "Slack ts 등. 원본 메시지 수정에 필요"]
  last_error text [null]
  sent_at timestamptz [null]
  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]
  indexes { (status, next_attempt_at) }
}
```
uncertain 건을 운영진이 검토한 기록은 `outbound_message_reviews`(검토자, 결정, 메모)로 둔다. UCanSign 발송은 상태 머신이 더 복잡하므로 별도 테이블로 둔다(§4.4).

### 3.5 공휴일
```dbml
Table holidays {
  date date [pk]
  name varchar(50) [not null]
  is_substitute bool [not null, default: false, note: "대체공휴일"]
}
```
Auto_monitor·ucansign이 소스에 하드코딩한 공휴일(2027년까지)을 대체한다. vacation 휴가 일수, ucansign 단위 기간·환불 계산, Auto_monitor 감시일 판정에 함께 쓴다.

### 3.6 외부 계정 식별자
```dbml
Table user_external_accounts {
  id uuid [pk]
  user_id uuid [not null, ref: > users.id]
  provider ExternalProvider [not null, note: "SLACK, DISCORD, ZEP"]
  workspace_id varchar(64) [null, note: "Slack team / Discord guild"]
  external_id varchar(100) [not null, note: "Slack U.., Discord snowflake, ZEP 닉네임"]
  cohort_id uuid [null, ref: > cohorts.id, note: "ZEP 닉네임처럼 기수 범위에서만 유일한 경우"]
  created_at timestamptz [not null, default: `now()`]
  indexes { (provider, workspace_id, cohort_id, external_id) [unique] }
}
```
이 테이블을 두면 `employees.slack_user_id`/`discord_user_id`와 `students.discord_id`를 모두 여기로 옮길 수 있다.
- **주의:** 컬럼에 NULL이 섞인 unique는 PostgreSQL에서 중복을 허용한다. PG15 이상의 `NULLS NOT DISTINCT`나 부분 인덱스를 쓴다.
- `oauth_accounts`(로그인 수단)와는 용도가 다르므로 분리한다.

### 3.7 외부 연동 자격증명
```dbml
Table integration_credentials {
  id uuid [pk]
  provider varchar(30) [not null, note: "SLACK_BOT, DISCORD_BOT, UCANSIGN, GOOGLE_WORKSPACE"]
  label varchar(50) [not null]
  encrypted_secret bytea [not null, note: "AES-GCM, 키는 환경변수/Secret Manager"]
  secret_fingerprint char(64) [not null, unique, note: "SHA-256, 중복 등록 방지"]
  metadata jsonb [null, note: "ucansign 템플릿 ID 목록 등"]
  is_active bool [not null, default: true]
  version int [not null, default: 1]
  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]
}
```
흡수 대상: Auto_monitor `system/connection`, ucansign `ucansign_accounts`, mentor Google refresh token.

### 3.8 이관용 레거시 ID 매핑
```dbml
Table legacy_id_mappings {
  source varchar(30) [not null, note: "mentor.firestore, exam.supabase, ucansign.d1 ..."]
  source_table varchar(50) [not null]
  legacy_id varchar(255) [not null]
  target_table varchar(50) [not null]
  target_id uuid [not null]
  indexes { (source, source_table, legacy_id) [pk] }
}
```
Calendar 이벤트 ID(예약 요청 ID의 해시), 시트 K열(세션 ID), UCanSign 요청 마커처럼 **외부에 박힌 ID**를 역추적할 때 쓴다.

---

## 4. 서비스별 추가 테이블

컬럼은 핵심만 적었다. 상세 근거는 `docs/analysis/<서비스>.md`를 참고한다.

### 4.1 Auto_monitor (출결 감시)
| 테이블 | 핵심 컬럼 | 비고 |
| --- | --- | --- |
| `cohort_class_hours` | cohort_id, weekday, start_time, end_time, break_start/end | 반복 수업 시간표. 감시 구간 |
| `cohort_monitor_settings` | cohort_id(PK), enabled, notifications_enabled, slack_log_channel_id, slack_notice_channel_id, alert_channels(jsonb), thresholds, ignored_zep_nicknames(text[]), revision | 기존 `cohorts.settings`. `revision`은 낙관적 잠금 |
| `slack_channel_routes` | channel_id, cohort_id, route_type(LOG/NOTICE) | ZEP 로그 채널은 기수 1개 전용(unique), 공지 채널은 공유 가능 |
| `student_monitoring_status` | student_id, status(ACTIVE/PAUSED/WITHDRAWN), from, until, reason | 명단 배열 안의 `monitoring` 필드 |
| `slack_inbound_events` | event_id(unique), channel_id, ts, payload(jsonb), received_at, processed_at | 웹훅은 저장만 하고 바로 200. 기존 inbox·receipts. 7일 정리 잡 |
| `monitor_engine_states` | cohort_id, date, generation, checkpoint(jsonb), slack_cursor, updated_at | 기존 `state/current`, `history/current` |
| `monitor_overrides` | cohort_id, student_id, date, kind, value, created_by | 운영진 수동 보정 |
| `attendance_daily_reports` | cohort_id, date, format_version, summary(jsonb) | 기존 dailyReports(v1~v6 혼재) |
| `attendance_daily_records` (권장) | student_id, date, absent_minutes, camera_off_minutes, first_seen_at, last_seen_at | 리포트 jsonb와 별도로 **정규화된 출결 데이터**. 통계·HRD 대조용 |
| 알림 발송 | → `outbound_messages` (§3.4) | 원본 Slack 메시지 수정에 `provider_message_id` 사용 |

### 4.2 exam (시험)
| 테이블 | 핵심 컬럼 | 비고 |
| --- | --- | --- |
| `question_categories` | id, parent_id, owner_scope, name | 트리 |
| `questions` | id, category_id, type(8종), stem(jsonb), points, created_by, deleted_at | 이미지는 URL 대신 `file_id`로 참조 |
| `question_answer_keys` | question_id(PK), answer_key(jsonb), grading_rules(jsonb) | **권한 분리를 위해 별도 테이블 유지** |
| `exams` | id, cohort_id, title, settings(jsonb), current_version_id, deleted_at | 시험 비밀번호는 평문 대신 해시 |
| `exam_sections` | exam_id, ordering, mode(FIXED/RANDOM), draw_count | |
| `exam_questions` | section_id, question_id, ordering, points | |
| `exam_versions` | id, exam_id, version_no, snapshot(jsonb), published_at, published_by | **발행 후 불변** |
| `exam_invitations` | id, exam_id, token(unique), code(char 8), max_uses, used_count, expires_at | `used_count`는 원자적 증가로 처리 |
| `exam_attempts` | id, exam_version_id, student_id, seed, status, ended_reason, started_at, deadline_at, submitted_at, score, passed | **부분 유니크**: 진행 중 응시 1건. raw SQL 마이그레이션 |
| `exam_attempt_items` | attempt_id, question_id, ordering, response(jsonb), points_awarded, graded_by | |
| `exam_attempt_events` | attempt_id, type, payload, created_at | 감사 로그 |
| 본인 확인 실패 제한 | → Redis | 기존 `roster_auth_failures` |

- exam의 `candidates`는 `students`로, `memberships`는 `user_roles`로 흡수한다.
- 미사용 테이블(`certificates*`)은 이관하지 않는다.

### 4.3 mentor (1:1 멘토링) — 초안 모델과 차이가 가장 큼
초안의 `mentoring_teams` / `mentees` / `sessions`(일지)는 **팀 단위 정기·프로젝트 멘토링**에 맞는 모델이다. 기존 서비스는 **수강생이 직접 슬롯을 예약하는 1:1 멘토링**이다. 두 모델은 공존할 수 있으므로 1:1 예약 쪽을 추가한다.

| 테이블 | 핵심 컬럼 | 비고 |
| --- | --- | --- |
| `mentor_cohorts` | mentor_id, cohort_id | 기존 `mentorCohorts[]` |
| `mentor_slots` | id, mentor_id, starts_at, ends_at, status(OPEN/RESERVED/CLOSED) | 30분 단위. `EXCLUDE USING gist (mentor_id with =, tstzrange(starts_at, ends_at) with &&)`로 겹침 방지 |
| `mentoring_booking_requests` | id, student_id, mentor_id, status, requested_minutes(30/60), message, counter_proposal(jsonb), replaced_request_id, decided_at, decided_by | 핵심 상태 머신. 변경 = 기존 요청 취소 + 새 요청 생성 |
| `mentoring_booking_slots` | request_id, slot_id | 60분 예약은 슬롯 2개 (기존 `slotId` + `secondarySlotId`) |
| `one_on_one_sessions` | id, request_id(unique), status(SCHEDULED/COMPLETED/NO_SHOW/CANCELLED), starts_at, ends_at, record(jsonb 또는 컬럼), calendar_event_id, meet_url, sheet_synced_at | 기존 `session-{requestId}`. **calendar_event_id는 기존 해시 값을 보존한다** |
| `one_on_one_session_notes` | session_id, body, author_id | 멘토 전용 내부 메모. 수강생에게 노출 금지 |
| `session_recordings` | session_id, file_id, kind(VIDEO/SUMMARY), drive_file_id, sync_status, next_check_at, attempts | 1시간 동기화 잡 큐. 최대 7일 재시도 |
| `cohort_mentoring_quotas` | cohort_id, base_minutes, allocation_policy, periods(jsonb), blocked_hours(jsonb) | 기존 `campQuotas` |
| `mentoring_grants` | student_id, minutes(음수 가능), reason, granted_by, created_at | 시간 추가·차감 이력 |
| `mentoring_settlement_closings` | bootcamp_id, month, mentor_id, snapshot(jsonb), closed_by, closed_at | `unique(bootcamp_id, month, mentor_id)` |
| `chat_threads` | id, student_id, mentor_id | `unique(student_id, mentor_id)` |
| `chat_messages` | thread_id, sender_id, body, created_at, read_at | 실시간 전달은 WebSocket/SSE + Redis |
| 메일·캘린더·시트 처리 | → `outbound_messages` | 기존 `*MailLogs`(1회 발송 키)는 `dedup_key`로 |

**결정 필요:** 초안의 `mentoring_sessions` / `mentoring_recordings`와 1:1 세션을 **하나의 세션 테이블**(`session_kind`: TEAM / ONE_ON_ONE)로 통합할지, 분리할지.
- 녹화·요약·기록 구조가 같으므로 `session_recordings`는 공유할 수 있다.
- 기존 녹화는 S3 업로드가 아닌 **Google Drive(Meet 자동 녹화)**다. 초안 `mentoring_recordings`의 `s3_key` 필수 조건과 맞지 않는다 → `files.storage = GOOGLE_DRIVE`로 표현한다.

### 4.4 ucansign (전자서명 서류 발송)
| 테이블 | 핵심 컬럼 | 비고 |
| --- | --- | --- |
| 계정 | → `integration_credentials` (provider=UCANSIGN) | 기존 키는 계정 ID를 associated data로 암호화되어 있다. 이관 시 재암호화 |
| `esign_template_mappings` | credential_id, document_type, template_id(varchar), field_manifest(jsonb) | 서류 5종 |
| `cohort_esign_settings` | cohort_id, credential_id | 기수에 배정된 UCanSign 계정 (기존 `camp_profiles`) |
| `esign_drafts` | cohort_id, mode(MOCK/LIVE), state(jsonb), version | `unique(cohort_id, mode)` |
| `esign_batches` | id, idempotency_key(unique), body_hash, mode, roster_coverage(jsonb), created_by | |
| `esign_jobs` | id, batch_id, student_id, document_type, channel(KAKAO/EMAIL), snapshot(jsonb), due_at, status | |
| `esign_dispatches` | job_id(unique), state(7종), claim_token, lease_expires_at, request_marker(unique), content_hash, provider_document_id(varchar), provider_status, participants(jsonb), next_check_at | `content_hash`는 부분 유니크. **request_marker 형식 `ucansign-console:<jobId>` 유지** |
| `esign_document_events` | student_id, document_type, generated_at, generated_by | 브라우저 PDF 생성 이력 |
| `provider_usage_counters` | provider, date, count | 일 6,000회 폴링 상한 |

- 모의(MOCK)와 실발송(LIVE) 이력은 상태 컬럼이 다르므로 섞이지 않게 한다.
- 실발송 상태 머신을 공통 `outbound_messages`에 넣을지 검토했지만, 필드와 상태가 많아 **별도 테이블을 권장**한다.

### 4.5 vacation → 수강생 신청 공통화
vacation이 쓰는 시트는 휴가뿐 아니라 결석, 지각, 조퇴, 중도포기, 출석인정이 함께 들어가는 **공용 이슈 시트**(30개 컬럼)다. 그래서 "휴가" 전용 테이블보다 **수강생 신청서 공통 테이블**을 권장한다.

| 테이블 | 핵심 컬럼 | 비고 |
| --- | --- | --- |
| `student_requests` | id, request_key(unique, 기존 결정적 UUID), content_hash, student_id(nullable), cohort_id, type(VACATION/ABSENCE/LATE/EARLY_LEAVE/DROPOUT/ATTENDANCE_CERT), start_date, end_date, reason, status(SUBMITTED/APPROVED/REJECTED), reviewed_by, reviewed_at, submitted_at | 기존 앱에는 승인 기능이 없다. 도입 여부 결정 필요 |
| `student_request_files` | request_id, file_id, kind(FORM_PDF/EVIDENCE) | PDF에 서명·생년월일이 들어 있으므로 `is_sensitive` |
| 시트 내보내기 | → `outbound_messages` (channel=GOOGLE_SHEETS) | 시트를 계속 원천으로 쓸지 결정 필요 |

- 기존 데이터에는 수강생 식별자가 없다(캠프+기수+이름). 그래서 이관 시 `student_id` 매칭 실패에 대비해 nullable로 두고, 원본 이름·캠프 텍스트를 보관한다(`legacy_*` 컬럼).
- 공개 익명 폼을 유지한다면 레이트 리밋(Redis)과 `request_key`로 중복을 막는다.

---

## 5. 인덱스·제약 체크리스트
- [ ] PostgreSQL은 **FK에 인덱스를 자동으로 만들지 않는다.** 조회가 많은 FK(`cohort_id`, `student_id`, `mentor_id` 등)에는 인덱스를 명시한다.
- [ ] 연결 테이블 unique: `mentoring_mentees(team, student)`, `project_team_members`, `level_based_class_students`, `mentor_cohorts`, `cohort_subject_instructors`
- [ ] Tortoise로 표현할 수 없는 제약은 raw SQL 마이그레이션으로 관리한다.
  - 부분 유니크 인덱스(진행 중 응시, 발송 content hash)
  - `EXCLUDE` 제약(멘토 슬롯 겹침)
  - `NULLS NOT DISTINCT`
  - `check(num_nonnulls(...) = 1)`
- [ ] 날짜 범위 check: `start_date <= end_date` (cohorts, cohort_subjects, schedules, classes, requests)
- [ ] 시간 컬럼은 모두 `timestamptz`. "하루" 경계는 Asia/Seoul 기준으로 앱에서 계산한다.

---

## 6. 확인이 필요한 질문
1. **부서가 데이터 소유 범위(테넌트)인가?** 예를 들어 문제은행을 부서별로 분리하는지.
2. **수강생도 `users` 계정(이메일 필수)을 갖는가?** exam은 무계정 응시, vacation은 익명이었다. 이메일 없는 수강생이 있다면 `users.email`을 nullable로 하거나 학생용 식별자가 따로 필요하다.
3. 운영 과정(`bootcamps`)과 HRD-Net 과정의 관계는 1:1인가, 1:N인가?
4. `cohorts.parent_id` / `is_derived`(파생 과정)의 정확한 의미, 그리고 한 기수에 파생 기수가 여러 개일 수 있는지.
5. 조교·멘토·강사 중 `employees`가 아닌 외부인이 담당자(`cohort_staffs`)가 될 수 있는가?
6. 멘토링: 팀 멘토링과 1:1 예약 멘토링을 모두 운영하는가? 세션 테이블을 통합할 것인가?
7. 휴가 등 수강생 신청에 **승인 워크플로**를 새로 도입하는가? 공용 이슈 시트는 계속 유지하는가?
8. RBAC를 `user_roles` 하나로 통일하는가, 아니면 `*_staffs` 담당자 테이블과 병행하는가?
