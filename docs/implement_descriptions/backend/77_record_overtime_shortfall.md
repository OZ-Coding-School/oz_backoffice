# 77. 기록 제출 시 잔여 부족 처리 (BE-2l)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A78 (A53 변경, A55·A56)
- 이전 기록: [76. 멘토 세션 목록 탭·기수 필터 (BE-2k)](76_mentor_session_views.md)

## 배경
FE-10b 기록 작성 화면을 정하다가 정책을 바꿨다. A53은 실제 진행 시간이 신청보다 길 때 초과분을 신청자(팀) 잔여에서 차감하고, 잔여가 모자라면 기록 제출을 거부했다. 사용자는 멘토가 이미 진행했으므로 기록은 항상 받아야 하고, 운영진이 정산할 때 참고만 하면 된다고 정했다(A78). 계좌 잔여는 DB CHECK로 음수가 될 수 없어, 모자란 분을 세션에 따로 남긴다.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `mentoring/domain/session.py` | `uncharged_overtime_minutes`, `note_uncharged_overtime`(완료·0보다 클 때만) |
| `mentoring/application/record_service.py` | 초과분 중 잔여만큼만 OVERTIME으로 차감하고, 나머지는 미차감 초과로 남긴다. 잔여가 0이면 원장은 그대로 |
| `mentoring/infrastructure/models/session.py`, `repositories.py` | 컬럼과 저장·조회 |
| `migrations/models/29_…_session_uncharged_overtime.py` | 컬럼 추가 + CHECK(null 또는 > 0이고 COMPLETED) |
| `docs/database_schema_v2.dbml` | 컬럼과 CHECK note |
| `mentoring/presentation/session_router.py` | 운영진 세션 응답에만 `uncharged_overtime_minutes` |
| `mentoring/presentation/settlement_router.py`, `application/settlement_export.py` | 정산 상세 항목에 같은 값, CSV 기본 열 끝에 '미차감 초과(분)' |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 생성 타입 갱신 |

## 주요 결정 (사용자 결정, A78)
- 잔여가 모자라도 기록 제출을 막지 않는다.
- 초과분은 잔여만큼만 차감하고 모자란 분은 세션의 미차감 초과 시간으로 남긴다. 계좌 잔여는 음수가 되지 않는다.
- 운영진 세션 응답과 정산 상세·CSV에 보여 정산 때 참고한다. 정산 금액은 지금처럼 실제 진행 시간 기준이다.
- 수강생·멘토 응답에는 넣지 않는다.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 902 passed (통합 테스트 포함)
  - 단위: 잔여 안 초과는 그대로 OVERTIME, 잔여보다 많으면 잔여만큼 차감 + 미차감 30분, 잔여 0이면 원장 없이 미차감만
  - 통합: 저장·조회 왕복, CHECK가 0과 완료가 아닌 상태를 막는다
  - API: 운영진 응답에만 필드, CSV 열 15개와 '미차감 초과(분)'
- 마이그레이션: 개발 DB에서 `aerich upgrade` → `aerich migrate`(No changes detected) → `aerich downgrade -v 29` → `aerich upgrade`
- DBML 파서(`@dbml/core` 11.x) 통과
- 프론트엔드: `typecheck`, `vitest` 225 passed

## 남은 작업
- FE-10b 세션 상세·기록 작성(초과·단축 안내)·수정·내부 메모
- 운영진 정산 화면(FE-14~)에서 미차감 초과 표시
