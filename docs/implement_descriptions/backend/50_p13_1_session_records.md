# 50. P13-1 세션 기록·내부 메모·미제출 목록

- 상태: 완료 (2026-11-13 병합)
- 관련 PR: #55
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P13 (P13-1)
- 이전 기록: [49. P12-3 Meet 멘토 공동 주최자 등록](49_p12_3_meet_cohost.md)

## 배경
P13은 PR 두 개로 나눴다(A53). 이번 PR은 멘토의 기록 제출(완료·노쇼)과 계좌 정산, 내부 메모, 운영진의 기록 미제출 목록을 붙인다. 녹화·전사·요약 수집·폴더 정리·중계는 P13-2에서 한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/session.py` | `submit_completed`(30분 단위 진행 시간·주제 100자·요약 필수 5,000자), `submit_no_show`(사유 선택), `edit_record`(주제·요약, 제출 후 7일), 예정 시작 이후만 |
| `mentoring/domain/balance.py`, `enums.py` | `overtime`(초과분을 잔여에서 사용, 부족하면 `insufficient_balance`), 원장 유형 `OVERTIME` |
| `mentoring/domain/note.py` | 내부 메모(세션당 하나, 5,000자) |
| `mentoring/infrastructure/models/note.py`, 마이그레이션 19 | `mentoring_session_notes`(세션 유니크, 본문 길이 CHECK), 원장 유형 CHECK에 `OVERTIME` 추가 |
| `mentoring/infrastructure/repositories.py` | 메모 리포지토리, 세션 `list_unrecorded` |
| `mentoring/application/record_service.py` | `SessionRecordService`: 제출·수정·메모·미제출 목록 |
| `mentoring/presentation/record_router.py`, `session_router.py` | API, 세션 응답의 기록 필드 |

**API**

| 대상 | 메서드·경로 | 내용 |
| --- | --- | --- |
| 담당 멘토 | `POST /api/v1/mentoring/sessions/{id}/record` | `{status: COMPLETED, duration, topic?, summary}` 또는 `{status: NO_SHOW, summary?}` |
| 담당 멘토 | `PATCH /api/v1/mentoring/sessions/{id}/record` | `{topic?, summary?}` 제출 후 7일 |
| 담당 멘토 | `GET`·`PUT /api/v1/mentoring/sessions/{id}/note` | 내부 메모 조회·저장 |
| 운영진 | `GET /api/v1/admin/cohorts/{cohort_id}/mentoring/sessions/unrecorded` | 예정 시작이 지났는데 기록 없는 세션 |
| 운영진 | `GET /api/v1/admin/cohorts/{cohort_id}/mentoring/sessions/{id}/note` | 내부 메모 조회 |

세션 응답에 `summary`(요약·노쇼 사유)·`record_duration_minutes`·`recorded_at`이 생겼고, 운영진 응답에는 Meet 실제 `actual_started_at`·`actual_ended_at`도 있다.

## 주요 결정 (사용자 결정, A53)
- 기록은 담당 멘토만, **예정 시작 시각 이후** 제출. 운영진은 **조회만**(대리 제출 없음).
- 실제 진행 시간은 **30분 단위, 신청보다 길어도 됨**. 계좌는 **실제 진행 시간 기준**: 짧으면 차이 REFUND, 길면 초과분 **OVERTIME**(잔여 부족 시 거부). 노쇼는 전액 REFUND(M28). 정산도 실제 진행 시간 기준(P14).
- **진행 시간·완료/노쇼는 처음 제출로 고정**, 주제·요약은 **제출 후 7일까지** 수정.
- 주제 100자(기본값 신청 주제)·**요약 필수 5,000자**, 요약은 수강생도 본다. 노쇼 사유는 선택.
- Meet 실제 시각은 **저장해 운영진에게 보여 주기만** 한다(제출을 막지 않음).

## 구현 세부
- **원장:** 진행 시간을 처음 제출로 고정하므로 신청당 REFUND·OVERTIME은 각각 최대 한 번이다. 기존 `(request_id, type)` 부분 유니크(M10)를 그대로 쓴다. 실제 = 신청이면 원장 변화가 없다.
- **트랜잭션:** 계좌 → 신청 → 세션 순서로 잠그고 같은 트랜잭션에서 세션·계좌·원장·감사 로그를 저장한다. 잔여 부족으로 거부되면 세션도 바뀌지 않는다.
- **노쇼 사유:** 세션 `body`에 둔다(완료면 요약). 노쇼에는 주제를 고칠 수 없다.
- **내부 메모 길이 5,000자:** 요약과 같은 상한으로 두었다.
- **권한:** 기록·메모 쓰기는 담당 멘토가 아니면 403 `not_session_mentor`. 운영진 메모 조회는 다른 기수 세션이면 404.
- **라우터 순서:** 운영진 `.../sessions/unrecorded`가 세션 라우터의 `.../sessions/{session_id}`로 해석되지 않도록 기록 라우터를 먼저 등록한다.
- **감사 로그:** `mentoring.session.record`·`record_edit`·`note_write`(메모는 본문 대신 길이만 남김).

## 검증
- 단위: 도메인(시작 전 거부, 30분 단위, 요약 필수, 신청보다 긴 진행, 두 번 제출 거부, 7일 경계, 노쇼 사유·주제 수정 불가, 취소 세션 거부, 메모 길이, OVERTIME·부분 REFUND), 서비스(짧게 → REFUND, 길게 → OVERTIME·잔여 부족 거부와 상태 유지, 같은 시간 → 원장 없음, 노쇼 전액 환불, 권한·시작 전·수정 기한, 메모 작성·수정·운영진 조회·다른 기수, 미제출 목록)
- 통합(PostgreSQL): 메모 왕복·세션당 하나·빈 본문 CHECK, 미제출 목록, OVERTIME 원장 허용·신청당 하나
- API: 시작 전 거부 → 미제출 목록 → 진행 시간 누락 422·수강생 403 → 제출(잔여 반영) → 재제출 거부 → 요약 수정 → 미제출 0 → 수강생 요약 보임·운영진 실제 시각 필드 → 메모(수강생 403, 운영진 조회)
- 마이그레이션 19: `upgrade` → `migrate`("No changes detected") → `downgrade -v 19` → `upgrade`, DBML 파서 검증
- GitHub Actions (PR #55): backend 잡 통과
- 사용자가 작업 완료를 확인했다(2026-11-13). 메모 상한 5,000자는 별도 변경 요청 없이 유지
- 전체 773 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 커밋 4개를 worktree에서 하나씩 검사했다(765 → 767 → 772 → 773 passed)

## 남은 작업
- P13-2: 녹화·전사·요약 수집(이벤트 + 보완 폴링), `멘토링 녹화/과정/기수/멘토 실명/YYYY-MM` 폴더 정리, 목록·스트리밍 중계(Range)
- P14: 정산(실제 진행 시간 기준, 정산 마감 후 수정 잠금은 P14에서 다시 본다)
- 멘토 안내(기록 제출 기한 알림 등)는 알림(M24) 결정 후
