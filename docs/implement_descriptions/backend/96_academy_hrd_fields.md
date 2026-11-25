# 96. 과정·기수 응답에 HRD 값 (BE-3p)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #151
- 관련 결정: `docs/decisions.md` A97 (F73·F74)
- 이전 기록: [95. 기수 요약 API (BE-3o)](95_cohort_summary.md)

## 배경
FE-17a 과정·기수 화면의 HRD 항목이 내부 UUID라 사람이 읽을 수 없었다. 사용자가 응답에 HRD 값을 더하기로 했다(A97).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `academy/presentation/admin_router.py` | 과정 응답에 `hrd_net_id`·`hrd_bootcamp_name`, 기수 응답에 `hrd_net_id`·`hrd_cohort_number`. 목록·단건·추가·수정 응답 모두 한 번의 IN 쿼리로 붙인다(기수는 HRD 회차 + HRD 과정을 함께 읽음) |
| `tests/api/test_academy_admin.py` | HRD 값과, HRD 훈련과정 ID를 비우면 null |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A97)
- 화면에서 HRD API를 따로 읽지 않고 응답에 더한다. 기존 UUID 필드는 그대로 둔다.

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 911 passed

## 남은 작업
- FE-17a 과정·기수 화면.
