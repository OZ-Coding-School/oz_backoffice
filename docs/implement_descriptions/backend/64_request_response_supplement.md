# 64. 신청 응답 보완: 단건 조회·확정 세션·취소 주체·차감 상태

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A66, F28 (FE-4a 착수 전 보완)
- 이전 기록: [63. 계정 종류를 수강생·멘토·운영진으로 나눔](63_account_type_member_split.md)

## 배경
FE-4a(수강생 신청 내역 목록·상세·취소)를 그리다 보니 신청 응답에 화면이 쓸 값이 모자랐다.
- 상세 페이지를 열 단건 조회가 없었다(목록에서 찾아야 했다).
- 승인된 신청의 확정 일시는 세션 API를 따로 불러야 알 수 있었다.
- 카드에 넣을 멘토 한 줄 소개가 없었다.
- 취소 안내("멘토가 취소했어요", "자동 취소")에 쓸 취소 주체가 저장되지 않았다.
- '차감 예정 / 차감됨 / 돌려받음' 표시를 프론트가 상태로 추측해야 했다(운영진 취소는 환불 선택이라 상태만으로 알 수 없다).

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `mentoring/domain/enums.py` | `MentoringCancelActor`(REQUESTER·MENTOR·STAFF·SYSTEM), `RequestBalanceState`(HELD·USED·RETURNED·NONE) |
| `mentoring/domain/request.py` | `canceled_by` 필드. `cancel(reason, *, now, by)`가 취소 주체를 받는다 |
| `mentoring/domain/balance.py` | `request_balance(entries)`: 신청의 원장 줄로 차감 상태·분을 정한다 |
| `mentoring/application/request_service.py` | 취소 경로마다 주체를 넘긴다. `get_for_user`: 단건 조회 권한 |
| `mentoring/application/request_cleanup.py` | 자동 취소·세션 자동 취소는 SYSTEM |
| `mentoring/infrastructure/models/request.py`, `repositories.py` | `canceled_by` 컬럼. 원장 `amounts_by_requests`, 세션 `map_by_requests`(각각 IN 쿼리 한 번) |
| `migrations/models/26_…_request_canceled_by.py` | 컬럼 추가 + CHECK. 데이터는 옮기지 않는다 |
| `mentoring/presentation/presenters.py` | `NameBook`에 멘토 한 줄 소개 |
| `mentoring/presentation/request_router.py` | 응답 필드 4개, `GET /mentoring/requests/{id}` |
| `docs/database_schema_v2.dbml` | `canceled_by`, `Enum MentoringCancelActor`, CHECK |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 다시 만들었다(F19) |

### 취소 주체

| 경로 | `canceled_by` |
| --- | --- |
| `POST /mentoring/requests/{id}/cancel` | 신청자면 REQUESTER, 담당 멘토면 MENTOR |
| `POST /mentoring/requests/{id}/change` (기존 신청) | REQUESTER |
| `POST /admin/cohorts/{id}/mentoring/requests/{id}/cancel` | STAFF |
| 대기 만료 작업, 멘토 비활성화·배정 종료·신청 받기 끄기·팀 담당 멘토 변경·팀 이탈·수강 종료·불가 시간 충돌로 인한 세션 취소 | SYSTEM |

A66 이전에 취소된 행은 비어 있다(`null`). 화면은 취소 시각만 보여 준다.

### 차감 상태 (`balance`)
신청 id로 원장을 모아 계산한다.
- 보류 = HOLD − RELEASE − USING
- 사용 = USING + OVERTIME − REFUND
- 돌려받음 = RELEASE + REFUND

보류가 남았으면 `HELD`(차감 예정), 아니면 사용이 남았으면 `USED`(차감됨), 아니면 돌려받은 시간이 있으면 `RETURNED`, 원장이 없으면 `NONE`이다. `minutes`는 그 상태의 분이다.
- 예: 운영진이 환불 없이 취소하면 USED, 짧게 진행해 일부 환불하면 USED(남은 분).

### API

| API | 내용 |
| --- | --- |
| `GET /mentoring/requests/{id}` | 신청자(1:1), 소속 팀원(팀 신청), 담당 멘토만. 그 밖과 없는 신청은 404 `request_not_found`(세션 단건과 같은 규칙) |
| 신청 응답 (수강생·멘토·운영진 공통) | `mentor_headline`, `canceled_by`, `session`(`id`·`starts_at`·`ends_at`, 승인된 신청만), `balance`(`state`·`minutes`) |

목록 응답은 쿼리가 두 번 늘어난다(세션 IN, 원장 IN). 원장 IN은 기존 유일 인덱스 `(request_id, type)`를 쓴다.

## 주요 결정 (사용자 결정, A66)
- 단건 조회·확정 세션·멘토 한 줄 소개를 모두 추가한다.
- 취소 주체를 저장해 보여 준다. 기존 행은 채우지 않는다.
- 차감 상태는 백엔드가 원장으로 계산해 내려준다.

## 발견한 문제와 해결
- 없음

## 검증
- **DBML:** `@dbml/core` 11 `dbmlv2` 파서로 통과했다.
- **개발 DB:** `aerich upgrade` → `aerich migrate`("No changes detected") → `aerich downgrade -v 26` → `aerich upgrade`
- **테스트**
  - 단위: 취소 주체 저장(사유 검증 실패 시 그대로), `request_balance` 7가지 원장 조합, 서비스 취소 경로별 주체(신청자·멘토·운영진·변경·대기 만료·자동 정리), 단건 조회 권한(신청자·멘토·팀원 허용, 다른 사람의 1:1·팀 밖·없는 신청 404)
  - 통합: `canceled_by` 저장 왕복과 CHECK 위반, `amounts_by_requests`, `map_by_requests`
  - API: 단건 조회 권한(404·401), 대기 HELD → 승인 USED + 확정 세션 → 운영진 환불 취소 STAFF·RETURNED, 신청자 취소 REQUESTER
- **로컬 검사 (compose `api`):** ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 878 passed.
- **프론트엔드:** 다시 만든 타입으로 `typecheck` 통과

## 남은 작업
- FE-4a: 신청 내역 목록·상세·취소 화면 (Figma 태블릿·모바일 먼저)
