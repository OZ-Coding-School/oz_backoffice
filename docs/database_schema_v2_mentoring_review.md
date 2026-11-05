# `database_schema_v2.dbml` 리뷰 — 멘토링 우선 이전 축소판

> **상태 (2026-11-05):** 리뷰와 결정 과정 기록이다. §1~§6은 리뷰 당시(테이블 33개) 기준이고 모두 처리됐다. 결정 결과는 §7과, 이후 추가 결정까지 포함한 `docs/decisions.md` §2(M1~M25)에 정리돼 있다.

대상: `docs/database_schema_v2.dbml` (테이블 33개, enum 21개)
비교 기준: 기존 mentor 서비스 분석(`docs/analysis/mentor.md`)

DBML 파서(`@dbml/core` 11.0.1)는 통과한다. 하지만 파서는 check 제약 안의 컬럼명이나 PostgreSQL 타입을 검증하지 않는다. 그래서 아래 §1 항목은 **실제 마이그레이션 단계에서 실패한다.**

---

## 1. 즉시 수정 (실행 시 오류)

| 위치 | 현재 | 문제 | 수정안 |
| --- | --- | --- | --- |
| L236-239 `educator_contracts` check | `num_nonnulls(mentor_id, instructor_id) = 1` | `mentor_id`/`instructor_id` 컬럼이 제거되어 **CREATE TABLE이 실패**한다. 더 큰 문제는 **계약이 어느 멘토·강사의 것인지 연결이 아예 없다는 점**이다 | 두 컬럼을 복원한다(`ref: > mentors.id`, `ref: > instructors.id`) |
| L337 `cohorts` check | `parent_id IS NULL OR parent_id <> id` | `parent_id` 컬럼이 제거되어 실패한다 | 파생 기수를 이번 범위에서 뺄 거면 check와 `CohortStatus.INACTIVE`의 note를 정리한다. 유지할 거면 컬럼을 복원한다 |
| L475 `mentoring_requests.topic` | `text(300)` | PostgreSQL `text`에는 길이 지정이 없다 | `varchar(300)` |
| L477-479 `desired_at_1~3` | `datetime` | PostgreSQL에 없는 타입이다 | `timestamptz` |
| L202, L216 `profile_image_url` | `uuid [unique]` | 이름은 URL인데 타입은 uuid다. 같은 이미지를 쓸 일도 없으니 unique도 불필요하다 | S3 key를 직접 저장한다면 `profile_image_key varchar(1024)`. 파일 테이블을 참조한다면 `profile_image_file_id uuid` + FK. unique 제거 |
| L669 `MentoringRequestStatus.APPROAVED` | 오타 | | `APPROVED` |
| L650 `StudentStatus.RESISTERED` | 오타 | | `REGISTERED` |
| L635 `ScheduleType` | 사용처 없음 | | 제거 |

---

## 2. 모델 변경에 대한 확인 (의도된 변경인지)

축소하면서 기존 mentor 서비스와 **동작 방식이 바뀐 부분**이 있다. 의도한 설계라면 그대로 가되, 이관·운영에 미치는 영향을 정리했다.

### 2.1 슬롯 예약 → 희망 일시 3개 신청
- 기존 방식: **멘토가 슬롯을 연다**(단건·반복, 오픈 금지 구간) → 수강생이 빈 슬롯을 고른다 → 멘토가 승인한다.
- 현재 스키마: 수강생이 희망 일시 1~3순위를 적어 신청한다 → 멘토가 하나를 골라 승인한다.
- 영향
  - 멘토가 가능한 시간을 표현할 곳이 없어서 반려가 늘어날 수 있다.
  - 기존 `mentorSlots` 데이터와 "같은 한국 날짜에 진행 중인 예약 1건" 규칙은 이관하지 않거나 재정의해야 한다.
  - **멘토 일정 겹침을 막을 장치가 없다.** 같은 멘토가 같은 시간에 두 건을 승인할 수 있다 → §3.6.

### 2.2 기간별 시간 정책 → 단일 잔여 시간 계좌
- 기존 방식: 기수 상시분 + **기간표**(기간별 분량, 만료, 진행 불가 시간, perPeriod/shared 배분) + 개인 충전(±, 유효기간)을 매번 계산했다.
- 현재 스키마: 수강생(또는 팀)별 계좌 하나와 증감 원장.
- 영향
  - **지급 시간의 유효기간(만료)을 표현할 수 없다.** "프로젝트 기간에만 쓸 수 있는 시간" 같은 정책이 필요하면 원장에 `expires_on`을 두거나, 계좌를 `period_type`별로 나눠야 한다.
  - 이관할 때는 기존 계산 결과(현재 잔여분)를 `STAFF_GRANT`/`USING` 원장으로 변환해야 한다. 원본 계산 로직(`quota.ts`)으로 이관 시점의 잔여분을 산출하는 스크립트가 필요하다.

### 2.3 빠진 기능
| 기존 기능 | 현재 스키마 | 확인 |
| --- | --- | --- |
| 월별 정산 마감 | 없음 (`cost_settlement_policy`만 있음) | 정산을 이번 이전 범위에 넣는지 |
| 멘토 전용 내부 메모 | 없음 | 필요하면 `mentoring_session_notes` 또는 `sessions.internal_memo` + 응답 스키마에서 수강생 제외 |
| 수강생-멘토 채팅 | 없음 | 이번 범위에서 제외인지 |
| Google Calendar 이벤트(초대·알림) | Meet space만 있음 | Calendar 초대 없이 Meet 링크만 줄 건지. 기존은 Calendar 이벤트 + Meet |
| 신청·승인·취소 메일, 일일 다이제스트 | 발송 기록·중복 방지 테이블 없음 | 메일을 보낸다면 아웃박스(`outbound_messages`)가 필요하다 → §4 |
| 변경 요청·멘토 역제안 | `CHANGE_REQUESTED` 상태값만 있음 | 누가, 어떤 시간으로 요청했는지 저장할 곳이 없다 → §3.5 |
| 운영진 대리 예약(협의 일정 직접 생성) | 신청자가 수강생으로 고정, 생성자 컬럼 없음 | §3.5 |

---

## 3. 테이블별 피드백

### 3.1 `cohort_mentoring_settings`
- `allow_team_mentoring`, `allow_1_on_1`에 기본값이 없다 → `default: false`.
- 기수 기본 제공 시간이 없다. 기존 `baseMinutes`에 해당한다. 수강생과 팀을 등록할 때 계좌에 자동 지급할 기준값으로 `default_1on1_minutes`, `default_team_minutes`를 두면 운영이 편하다.
- 신청 규칙 값도 여기에 두는 게 자연스럽다. 예를 들어 `min_lead_hours`(기존 24시간 마감), `allowed_durations`(30/60분), `max_active_requests`(동시 신청 수 제한).
- `updated_at`이 nullable인데 다른 테이블(`not null default now()`)과 통일하자. 이 테이블 외에 멘토링 테이블 전부에 해당한다.
- `id`와 `cohort_id unique`가 둘 다 있다. `cohort_id`를 PK로 써도 된다(선택).

### 3.2 `cohort_mentoring_block_times`
- 기존 `blockedTimes`에는 **요일**(`weekdays[]`)과 특정일(`onDate`)이 있었다. 지금은 적용 기간 안의 매일에 같은 시간대가 적용된다. 예를 들어 "매주 월요일 오전 금지"를 표현하려면 `weekdays smallint[] null`(null이면 매일)을 추가한다.
- `reason varchar(200)`. 수강생에게 "이 시간은 신청할 수 없는 이유"를 보여줄 때 쓴다.
- check를 추가한다: `period_start <= period_end`, `start_time < end_time`.
- 팀 멘토링과 1:1 중 한쪽에만 적용해야 하는 경우가 있다면 `applies_to`(ALL/TEAM/ONE_ON_ONE) 컬럼을 둔다.

### 3.3 `cohort_mentors`
- `unique(mentor_id, cohort_id, period_type)`: 한 기수에 프로젝트 기간이 여러 번(중간·최종 프로젝트) 있으면 **같은 멘토를 다시 배정할 수 없다.** 그럴 수 있다면 unique를 빼고 기간 겹침 검사(앱 레벨 또는 `EXCLUDE`)로 바꾼다.
- check 추가: `start_date <= end_date`.
- `updated_at`이 없다. `is_active`를 토글하려면 필요하다.
- 정산하려면 단가가 필요하다. 단가는 `educator_contracts.pay_rate`에 있지만, 계약과 멘토의 연결이 빠져 있어서 지금은 계산할 수 없다(§1). 기수마다 단가가 다르다면 `cohort_mentors.contract_id` 참조도 고려하자.

### 3.4 `mentoring_balance_accounts` / `mentoring_balance_transactions`
원장 방식(증감 이력 + 현재 잔액)은 좋은 선택이다. 기존에는 매번 다시 계산해서 비용이 컸고 결과가 들쭉날쭉했다. 보완할 점은 아래와 같다.
- **`remaining_minutes`는 중복 저장이다.** `total - used`와 어긋날 위험이 있다. 생성 컬럼으로 바꾸거나 `check(remaining_minutes = total_minutes - used_minutes)`를 건다.
- 음수 잔액을 허용할지 정해야 한다. 허용하지 않는다면 `check(remaining_minutes >= 0)`. 기존에는 회수(음수 충전)가 가능했다.
- 타입: `smallint`(최대 32,767분 ≈ 546시간)은 누적값으로는 여유가 적다 → `integer`.
- 원장 테이블에 다음 컬럼이 필요하다.
  - `request_id`/`session_id`(nullable). **어떤 신청이나 세션 때문에 차감·환불됐는지** 추적한다.
  - `created_by`(운영진 부여·조정 시 담당자). `audit_logs`로도 가능하지만 원장 자체에 있는 편이 조회가 쉽다.
  - **중복 차감·환불 방지**: 부분 유니크 `(request_id, type) WHERE type IN ('USING', 'REFUND')`. 승인 버튼을 두 번 누르거나 재시도할 때 두 번 차감되는 걸 막는다.
- 동시성: 차감할 때 계좌 행을 `SELECT … FOR UPDATE`로 잠그고, 잔액 갱신과 원장 추가를 한 트랜잭션에서 처리한다. 원장 행에 `after_balance`를 남기는 지금 구조는 이 방식과 잘 맞는다.
- **차감 시점을 정해야 한다.** 신청 시점(보류) / 승인 시점 / 진행 완료 시점 중 언제인가? `cost_settlement_policy = ACTUAL_DURATION`이면 실제 진행 시간과 신청 시간의 차이를 정산 단계에서 조정(`STAFF_ADJUST` 또는 `REFUND`)하는지도 정의해야 한다. 지금 enum으로는 "신청 시 보류(HOLD) → 확정/해제"를 표현할 수 없다. 신청 단계에서 잔액을 잡아둬야 한다면 `HOLD`/`RELEASE` 유형을 추가한다.
- note가 두 테이블 모두 "멘토링 잔여 시간"이다 → 원장 쪽은 "멘토링 시간 증감 이력"으로.
- check 제약은 `num_nonnulls(student_id, team_id) = 1`로 줄여 쓸 수 있다.

### 3.5 `mentoring_teams` / `mentoring_team_members` / `mentoring_requests`
- **팀 번호 중복**: `unique(cohort_id, team_number)`이라 같은 기수의 정기 팀과 프로젝트 팀이 번호를 나눠 써야 한다. 유형별로 번호를 매긴다면 `unique(cohort_id, period_type, team_number)`.
- `mentoring_teams.name varchar(10)`은 짧다 → 30~50.
- 팀에 담당 멘토가 없다. 팀 신청 때 아무 멘토에게나 신청할 수 있게 한 의도라면 괜찮다. 고정 담당이라면 `mentor_id`를 둔다.
- 앱 레벨 검증이 필요한 것들
  - 팀원(`students.cohort_id`)과 팀(`cohort_id`)은 같은 기수여야 한다.
  - 같은 `period_type`의 팀에 중복 소속되면 안 된다.
  - 팀 신청자(`requester_id`)는 그 팀의 팀원이어야 한다.
  - `mentor_id`는 해당 기수의 활성 `cohort_mentors`여야 한다.
- `mentoring_requests`에 추가할 컬럼
  - `decided_at`, `decided_by`(승인·반려 시각과 처리자)
  - `canceled_at`, `canceled_by`, `cancel_reason`(현재는 반려 사유만 있다)
  - `created_by`(운영진이 대신 신청한 경우)
  - check: `duration IN (30, 60)` 또는 `duration > 0`
  - 인덱스: `(mentor_id, status)`, `(requester_id, created_at)`, `(team_id)`
- **변경 요청(`CHANGE_REQUESTED`)의 내용을 저장할 곳이 없다.** 누가(수강생/멘토) 어떤 사유로 어떤 새 희망 일시를 제안했는지가 필요하다. 두 가지 방법이 있다.
  - (a) 기존처럼 **변경 = 기존 신청 취소 + 새 신청 생성** + `replaced_request_id`. 상태값 `CHANGE_REQUESTED`는 불필요해진다.
  - (b) `mentoring_request_changes(request_id, requested_by, reason, desired_at_1~3, status)` 테이블.
  - 단순한 쪽은 (a)다.
- 희망 일시를 컬럼 3개로 두는 방식은 단순해서 괜찮다. check `desired_at_1 < desired_at_2`처럼 순서까지 강제할 필요는 없다. 다만 **어떤 순위가 채택됐는지** 남기고 싶으면 `selected_rank smallint`를 둔다(세션 `starts_at`으로도 추정할 수는 있다).

### 3.6 `mentoring_sessions`
- **`mentor_id`가 없다.** 멘토별 일정 조회, 정산, 겹침 방지에 모두 필요하다. 신청을 거쳐 조인할 수도 있지만 비정규화하는 편이 낫다. 그러고 나서 `EXCLUDE USING gist (mentor_id WITH =, tstzrange(starts_at, ends_at) WITH &&) WHERE (status <> 'CANCELED')`로 멘토 일정 겹침을 DB 수준에서 막는다(§2.1의 문제 해결).
- `request_id not null`이므로 모든 세션은 신청을 거쳐야 한다. 운영진이 직접 일정을 잡는 경우에도 신청 행을 만들고 바로 승인 처리하는 흐름이면 괜찮다. 이때 `mentoring_requests.created_by`가 필요하다.
- `IN_PROGRESS` 상태는 시각에 따라 저절로 바뀌는 값이라 저장하려면 별도 잡이 필요하다. 조회 시점에 `starts_at ≤ now < ends_at`로 계산하는 편이 단순하다.
- 녹화 수집 잡을 위한 컬럼이 없다. 기존은 1시간 주기로 최대 7일간 재시도했다. 워커가 "다음에 확인할 세션"을 고를 수 있게 `recording_next_check_at`, `recording_check_attempts`를 두거나, `recording_status`와 `ends_at`으로 대상을 고르는 규칙을 정한다. 어느 쪽이든 `(recording_status, recording_next_check_at)` 인덱스가 필요하다.
- `recording_status`(세션)와 `mentoring_artifacts.status`(파일)의 역할 구분을 note로 명확히 하자. 예: 세션 = Meet 녹화 진행 상태, 아티팩트 = 파일 수집·보관 상태.
- `google_space_name`은 unique로 둔다.
- check 추가: `starts_at < ends_at`.
- `title`이 not null인데 "미기재시 자동입력"이므로 괜찮다. `topic`은 신청의 `topic`(300자)과 길이가 다르다(100자) → 맞춘다.

### 3.7 `mentoring_session_participants`
- note는 "참여 체크용"인데 **출석 여부 컬럼이 없다.** 행이 있으면 참석으로 보는 방식이라면 "참석 예정이지만 아직 체크 전"과 "불참"을 구분할 수 없다. `attendance`(EXPECTED / ATTENDED / ABSENT) 컬럼을 추가하고, 세션을 만들 때 팀원 전원(1:1은 신청자)을 EXPECTED로 넣는 방식을 권장한다. `NO_SHOW`는 세션 상태와 참석자별 상태 두 곳에 기록된다.

### 3.8 `mentoring_artifacts`
- `file_id varchar(1024)`는 이름과 내용이 다르다 → `storage_key` 등으로 바꾼다. **어느 저장소인지**(Google Drive file id / S3 key)를 구분하는 `storage` 컬럼이 필요하다. Meet 자동 녹화는 처음에 Drive에 생기기 때문이다.
- `unique(session_id, storage, storage_key)`. 수집 잡이 재실행될 때 중복 행이 생기지 않게 한다.
- 멘토에게 Drive 열람 권한을 줬는지 여부(`share_status`)는 기존 기능에 있었다. Drive 공유를 계속 쓰는지 확인이 필요하다.
- 녹화 영상이 `is_sensitive` 성격이라면 presigned URL 만료 정책을 note에 적어 두자.

---

## 4. 멘토링 이전에 함께 필요한 것 (스키마 외부 포함)

| 항목 | 필요한 이유 | 제안 |
| --- | --- | --- |
| 알림 발송 기록 | 신청·승인·반려·취소 메일, 다이제스트, Meet 생성 재시도. 기존에는 1회 발송 키로 중복을 막았다 | `outbound_messages`(dedup_key unique, status) 도입. 메일을 아예 안 보낸다면 불필요 |
| 정산 마감 | 기존 월별 정산 확정 스냅샷 | `mentoring_settlement_closings(mentor_id, month, total_minutes, total_amount, snapshot, closed_by)` |
| 레거시 ID 매핑 | 기존 Firestore 문서 ID(예약·세션) ↔ 새 uuid. 기존 Calendar 이벤트와 시트 행 역추적 | `legacy_id_mappings` |
| Google 자격증명 | Meet REST 호출용 회사 계정 refresh token | 환경변수로 시작해도 무방 |
| 멘토 대리 보기 | 운영진 미리보기(읽기 전용) | `user_roles.expires_at` 활용 + 감사 로그 `impersonator_user_id` |

---

## 5. 정리 대상 (기능 영향 없음)
- 이전 리뷰용 주석과 note가 남아 있다: `[수정]`, `[추가]`, `smallint → integer (원)`, `s3_key → files 참조`, `Auto_monitor managers/assistants 대체`, `ucansign 환불 계산` 등. 최종본에서는 컬럼 의미만 남긴다.
- `cohort_staffs.receives_alerts`는 출결 감시 전용이다. 멘토링 범위에서는 불필요하니 출결 기능을 이전할 때 다시 넣는다.
- `user_external_accounts`에서 `cohort_id`가 빠졌다. 그래서 unique가 `(provider, workspace_id, external_id)`가 되어 **ZEP 닉네임이 기수가 달라도 중복될 수 없다.** 멘토링과는 무관하므로, 출결 이전 때 `workspace_id`에 기수 ID를 넣는 규칙을 쓰거나 컬럼을 복원한다.
- `users.email` unique는 대소문자를 구분한다 → `lower(email)` 유니크 인덱스 또는 `citext`.
- enum 표기 혼용: `CANCELED`(세션·신청)와 `CANCELLED`(다른 곳)가 섞일 수 있으니 한쪽으로 통일한다. 현재 파일 안에서는 `CANCELED`로 일관되어 있다.

---

## 6. 확인 질문
1. 슬롯 예약 → 희망 일시 신청 전환은 의도된 변경인가? 멘토가 가능한 시간을 등록하는 기능이 필요한가?
2. 지급 시간에 **유효기간(기간별 만료)**이 필요한가?
3. 잔여 시간 **차감 시점**은 신청 / 승인 / 완료 중 언제인가? 신청 시 보류가 필요한가?
4. 월별 정산 마감, 내부 메모, 채팅, 메일 알림 중 이번 이전 범위에 포함되는 것은?
5. Google Calendar 초대 없이 Meet 링크만 제공하는가?
6. 한 기수에 같은 멘토가 같은 유형(프로젝트)으로 여러 번 배정될 수 있는가?

---

## 7. 결정 및 반영 내역

| # | 항목 | 결정 | 반영 |
| --- | --- | --- | --- |
| Q1 | 예약 방식 | 희망 일시 신청 + 멘토 가능 시간 등록 | `mentor_availabilities`(요일별 반복), `mentor_unavailable_periods`(예외 불가 일정) 추가. `mentoring_sessions.mentor_id` + EXCLUDE로 멘토 일정 겹침 방지 |
| Q2 | 시간 만료 | 기간 유형별 계좌 분리 | 계좌에 `period_type`, `valid_from`, `valid_until`. unique (수강생 또는 팀, 유형) |
| Q3 | 차감 시점 | 신청 시 HOLD → 승인·세션 생성 시 USING, 승인 전 반려·취소 시 RELEASE, 승인 후 취소 시 REFUND. 음수 잔액 불가 | 계좌에 `held_minutes` 추가, 잔여 = total − held − used ≥ 0. 원장에 `request_id`, `created_by`, `after_held` 추가, `(request_id, type)` 유니크로 중복 처리 방지 |
| Q4 | 이전 범위 | 정산 마감, 내부 메모, 채팅 포함. 알림은 보류 | `mentoring_settlements`, `mentoring_settlement_items`, `mentoring_session_notes`, `mentoring_chat_threads`, `mentoring_chat_messages` 추가. 알림은 TODO 주석 |
| Q5 | 계약·단가 | 계약은 체결 여부만 관리(가입 전 계약 가능). 단가는 기수 배정별 | `educator_contracts`: 상대방 정보 + 가입 후 `user_id` 연결, 단가 컬럼 제거, 깨진 check 제거. `cohort_mentors`에 `pay_unit`, `pay_rate` |
| Q6 | 멘토 재배정 | 같은 기수·유형에 여러 번 가능 | unique 제거, 활성 배정끼리 기간 겹침 방지(EXCLUDE) |
| Q7 | Calendar | Meet만 사용 | 변경 없음 |
| Q8 | 진행 상태·녹화 | IN_PROGRESS는 Meet 이벤트로 저장. 녹화는 Drive 원본을 백엔드가 중계(멘토에게 Drive 권한 없음). 수집은 이벤트 + 상태로 판단 | 세션에 `google_conference_record_name`, `actual_started_at`, `actual_ended_at`. `mentoring_artifacts.drive_file_id` + `(session_id, drive_file_id)` 유니크. `(recording_status, ends_at)` 인덱스 |
| Q9 | 참석 체크 | 개인별 출석은 저장하지 않고 세션 상태(완료/노쇼)로만 판단 | `mentoring_session_participants` 제거 |
| Q10 | 팀 | 유형별 번호, 담당 멘토 고정, 같은 유형 팀 중복 소속 불가 | `mentoring_teams.mentor_id`, unique(cohort, period_type, team_number). `team_members.period_type` + unique(student, period_type) |
| Q11 | 신청 변경 | 취소 + 새 신청. 반려·취소 시각과 사유만 기록. 대리 신청 없음 | `replaced_request_id`, `rejected_at`, `canceled_at`, `cancel_reason` 추가. `CHANGE_REQUESTED` 제거 |
| Q12 | 기수 설정 | 기본 지급 시간, 신청 마감, 허용 진행 시간, 대기 중 신청 수 제한. 금지 시간대에 사유 | `cohort_mentoring_settings` 컬럼 5개 추가. `cohort_mentoring_block_times.reason` 추가 |
| Q13 | 저장소·파생 기수 | GCS 사용, 객체 이름을 직접 저장 (변경 2026-11-05: **AWS S3**, decisions C5~C7). 파생 기수는 이번 범위에서 제외 | `profile_image_key`, `contract_files.storage_key`. cohorts의 parent_id check 제거 |
| Q14 | 정리 | `receives_alerts`·외부 계정 제거, 이메일은 소문자로 정규화 | `user_external_accounts`, `ExternalProvider` 제거. `check(email = lower(email))`. 리뷰용 주석과 오래된 note 정리, enum 오타 수정, 미사용 `ScheduleType` 제거 |
