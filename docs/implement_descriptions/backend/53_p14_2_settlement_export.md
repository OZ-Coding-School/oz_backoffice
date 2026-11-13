# 53. P14-2 정산 CSV 내보내기·멘토 정산 조회

- 상태: 완료 (2026-11-13 병합)
- 관련 PR: #58
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P14 (P14-2)
- 이전 기록: [52. P14-1 정산 집계·조회·마감](52_p14_1_settlements.md)

## 배경
P14의 두 번째 PR이다(A55). 운영진의 정산 CSV 내보내기와 멘토 본인의 정산 조회를 붙인다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/application/settlement_export.py` | `SettlementExporter`: 명세 한 줄 = CSV 한 행. 이름·세션 정보를 묶어 한 번씩 조회 |
| `mentoring/application/settlement_service.py` | 멘토 본인 목록·상세(마감된 것만), 목록에 명세 묶어 읽기 옵션 |
| `mentoring/infrastructure/repositories.py` | 멘토의 마감된 정산, 기수·월 정산 + 명세 한 번에 |
| `mentoring/presentation/settlement_router.py` | CSV 두 가지, 멘토 조회 |

**API**

| 대상 | 경로 |
| --- | --- |
| 운영진(`mentoring.settlement.close`, 기수 범위) | `GET /api/v1/admin/cohorts/{cohort_id}/mentoring/settlements/export.csv?month=YYYY-MM&columns=` (기수·월 전체) |
| 운영진 | `GET /api/v1/admin/cohorts/{cohort_id}/mentoring/settlements/{id}/export.csv?columns=` (정산서별) |
| 멘토 본인 | `GET /api/v1/me/mentor-settlements`, `GET /api/v1/me/mentor-settlements/{id}` (마감된 것만, 명세 포함) |

**CSV 열**
- 기본(항상): 과정, 기수, 멘토, 정산 월, 정산 상태(집계 중·마감), 진행 일시(KST), 신청자(1:1 수강생 이름·팀 이름), 유형(진행·노쇼), 정산 기준(실제 진행·신청 시간), 정산 시간(분), 단가 단위(시급·회당), 단가(원), 금액(원), 세션 ID
- 선택(`columns`, 쉼표 구분): `topic`(주제), `summary`(요약), `recorded_minutes`(기록한 진행 시간), `meet_started_at`·`meet_ended_at`(Meet 실제 시작·종료). 모르는 이름이면 422 `invalid_export_columns`

## 주요 결정 (사용자 결정, A56)
- CSV는 **기수·월 전체와 정산서별 둘 다**.
- **기본 열은 항상, 나머지는 선택**.
- 멘토는 **마감된 정산의 목록과 명세**를 본다(CSV는 운영진만).

## 구현 세부
- **엑셀 호환:** UTF-8 BOM, `text/csv; charset=utf-8`, `Content-Disposition: attachment`(UTF-8 파일 이름 `멘토링정산_YYYY-MM[_멘토].csv`), `Cache-Control: private, no-store`. 쉼표가 든 요약도 CSV 규칙대로 따옴표 처리된다.
- **행 순서:** 멘토 → 진행 일시.
- **조회 수:** 기수·월 전체 CSV도 정산 1회 + 명세 1회 + 세션·신청·수강생·팀·멘토·회원·기수 각 1회로, 멘토·세션 수와 무관하게 쿼리 수가 일정하다.
- **멘토 조회:** 집계 중(DRAFT)이거나 다른 멘토의 정산이면 404로 숨긴다. 멘토 프로필이 없으면 404.

## 검증
- 단위: 멘토 본인 조회(집계 중 숨김 → 마감 후 목록·명세, 프로필 없음 404)
- API: 기수·월 CSV(BOM·헤더 선택 열·멘토·신청자·금액·쉼표 요약·정산 상태), 잘못된 열 422, 정산서별 CSV 기본 14열, 수강생 403, 멘토 조회 마감 전 빈 목록 → 마감 후 목록·명세, 멘토가 아니면 404
- GitHub Actions (PR #58): backend 잡 통과
- 사용자가 작업 완료를 확인했다(2026-11-13)
- 전체 798 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 코드 커밋을 worktree에서 검사했다(798 passed)
- 스키마 변경 없음

## 남은 작업
- P15 채팅
