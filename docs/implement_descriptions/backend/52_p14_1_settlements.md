# 52. P14-1 정산 집계·조회·마감

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P14 (P14-1)
- 이전 기록: [51. P13-2 녹화·전사·요약 수집·폴더 정리·중계](51_p13_2_meet_artifacts.md)

## 배경
P14는 PR 두 개로 나눴다(A55). 이번 PR은 운영진의 정산 집계·조회·마감이다. CSV 내보내기와 멘토 본인 조회는 P14-2에서 한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/settlement.py` | 정산 시간(`billable_minutes`), 금액(`session_amount`: 시급 내림·회당), 정산·명세, DRAFT 다시 집계·CLOSED 마감 |
| `mentoring/infrastructure/models/settlement.py`, 마이그레이션 21 | `mentoring_settlements`(멘토 × 기수 × 월 유니크), `mentoring_settlement_items`(세션당 하나) + CHECK |
| `mentoring/infrastructure/repositories.py` | 정산 리포지토리(명세 통째로 교체), 정산 대상 세션, 멘토별 미제출, 세션 `get_many` |
| `mentoring/application/settlement_service.py` | 집계·조회·마감 |
| `mentoring/presentation/settlement_router.py` | API |

**API** (`mentoring.settlement.close`, 기수 범위)

| 메서드·경로 | 내용 |
| --- | --- |
| `POST /api/v1/admin/cohorts/{cohort_id}/mentoring/settlements/aggregate` `{month: "YYYY-MM"}` | 집계(다시 집계). 응답에 정산서·건너뛴 세션·이미 마감된 정산 |
| `GET /api/v1/admin/cohorts/{cohort_id}/mentoring/settlements?month=` | 목록 |
| `GET /api/v1/admin/cohorts/{cohort_id}/mentoring/settlements/{id}` | 상세(명세, 세션 시작 시각순) |
| `POST /api/v1/admin/cohorts/{cohort_id}/mentoring/settlements/{id}/close` `{confirm}` | 마감. 기록 미제출 세션이 있으면 `applied=false`와 목록 |

## 주요 결정 (사용자 결정, A55)
- 정산 단위 **멘토 × 월 × 기수**(스키마에 `cohort_id` 추가, 기수 범위 권한).
- 정산 시간은 **배정의 정산 기준**: 실제 진행이면 기록한 진행 시간, 신청 시간이면 신청 시간. 수강생 계좌 차감은 A53대로 항상 실제 진행.
- 집계·마감은 **운영진 수동**. 그 달까지 기록된 세션 중 다른 정산에 없는 것을 모으므로 **마감 뒤 늦게 기록된 세션은 다음 정산**에 들어간다.
- 마감 때 기록 미제출 세션이 있으면 **경고 후 확인하면 마감**.
- 마감 뒤에도 세션 **주제·요약 수정(7일)은 허용**(금액 영향 없음) — 기록 수정 코드는 바꾸지 않았다.

## 구현 세부
- **대상 세션:** 그 기수(신청자 기수)에서 예정 시작이 그 달 말(KST 다음 달 1일 00:00) 이전이고 기록(완료·노쇼)이 끝난 세션 중 **다른 정산 명세에 없는 것**. 그래서 지난달 미제출이었다가 마감 뒤 기록된 세션도 이번 달 정산에 들어간다.
- **배정:** 세션 시작일(KST)에 유효한 그 기수 배정(비활성 포함, 여럿이면 가장 최근 시작). 없으면 건너뛰고 `assignment_not_found`로 알린다.
- **금액:** 시급 `floor(단가 × 분 / 60)`, 회당 단가, 노쇼는 배정의 노쇼 고정 금액(정산 시간 0). 정산 기준·단가 단위·단가를 명세에 스냅샷.
- **다시 집계:** DRAFT는 명세를 통째로 새로 계산한다(대상이 없어져도 기존 DRAFT는 0건으로 갱신). 마감된 정산은 건드리지 않고 `closed`로 돌려준다. 새로 만들 정산서에 넣을 세션이 없으면 만들지 않는다.
- **중복 정산 방지:** 명세의 세션 유니크(DB)와 다른 정산에 든 세션 제외(서비스).
- **감사 로그:** `mentoring.settlement.aggregate`·`close`(마감 때 미제출 수 포함).

## 검증
- 단위: 도메인(정책별 시간, 내림 경계 16666.5 → 16666·166.68 → 166, 회당, 월 넘김, 합계, 마감 후 변경 거부), 서비스(실제 진행·노쇼 고정 금액·다음 달·미제출 제외, 다시 집계 같은 정산서, 신청 시간 정책, 마감 경고·확인·두 번 마감 거부, 마감 뒤 늦은 기록 → 다음 달, 배정 없음 건너뜀, 다른 기수 404)
- 통합(PostgreSQL): 정산 대상·미제출 조회, 정산 저장·명세 교체·다른 정산 제외, 세션당 명세 하나(유니크), 마감 CHECK·1일 CHECK·시급·회당만 CHECK
- API: 잘못된 월 422, 수강생 403, 집계(금액·멘토 이름), 목록·상세, 마감 미리보기(미제출) → 확인 마감, 다시 집계 시 마감된 정산 표시
- 마이그레이션 21: `upgrade` → `migrate`("No changes detected") → `downgrade -v 21` → `upgrade`, DBML 파서 검증
- 전체 796 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 코드 커밋 4개를 worktree에서 하나씩 검사했다(790 → 791 → 795 → 796 passed)

## 남은 작업
- P14-2: CSV 내보내기, 멘토 본인 조회(마감된 정산만)
