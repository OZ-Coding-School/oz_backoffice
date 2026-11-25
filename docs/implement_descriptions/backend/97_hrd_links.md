# 97. HRD 연결 정보 (BE-3q)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #153
- 관련 결정: `docs/decisions.md` A98 (F73·F75, D6)
- 이전 기록: [96. 과정·기수 응답에 HRD 값 (BE-3p)](96_academy_hrd_fields.md)

## 배경
FE-17b HRD 과정 화면은 HRD 과정마다 연결된 운영과정·회차 수, 회차마다 연결된 기수를 보여 준다(F75). 기존 응답에 없어 필드를 더한다(A98).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `academy/presentation/admin_router.py` | HRD 과정 응답에 `bootcamps`(대표로 둔 운영과정 id·이름·코드)·`cohort_count`, HRD 회차 응답에 `linked_cohorts`(연결 기수 id·운영과정 id·이름·기수 번호). 목록·단건·추가·수정 응답 모두 IN 쿼리로 붙인다 |
| `tests/api/test_academy_admin.py` | 연결 운영과정·회차 수·연결 기수 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A98)
- 연결 조회 API를 따로 두지 않고 기존 응답에 더한다.

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 911 passed

## 남은 작업
- FE-17b HRD 과정 화면.
