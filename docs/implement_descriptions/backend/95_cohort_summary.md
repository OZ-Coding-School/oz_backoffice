# 95. 기수 요약 API (BE-3o)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #150
- 관련 결정: `docs/decisions.md` A96 (F73·F74)
- 이전 기록: [94. 법정공휴일 동기화 (BE-3n)](94_public_holiday_sync.md)

## 배경
FE-17a 학사 > 과정·기수의 기수 패널에 기수 운영 정보(수강생 상태별 인원·배정 멘토·담당자)를 보여 달라는 요청에 따라, 여러 컨텍스트에 흩어진 값을 한 번에 주는 요약 API를 먼저 만든다(A96).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `academy/application/cohort_summary.py` | 요약 값(`CohortSummary`: 수강생 인원·멘토·담당자)과 `CohortSummaryReader` 포트 |
| `app/composition/cohort_summary.py` | `CohortSummaryComposer`: 명단(원본에서 빠진 행 제외)으로 전체·가입 연결·수강 상태별 수, 활성 기수 배정 + 멘토 프로필 + 회원 이름, 기수 담당(COHORT)·과정 담당(COURSE) 배정 + 직원 + 직위 + 회원 이름(한 사람은 한 번, 기수 담당 먼저) |
| `academy/presentation/admin_router.py` | `GET /admin/cohorts/{id}/summary`(`academy.cohort.read`, 기수 범위, 없는 기수 404) |
| `main.py` | `app.state.cohort_summary` 배선(B10) |
| `tests/api/test_cohort_summary.py` | 인원·멘토·담당자, 담당이 아닌 기수 403 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A96)
- 기수 요약 API 하나, 권한은 기수 조회(`academy.cohort.read`, 기수 범위).
- 멘토·담당자는 이름 목록. 멘토링 설정 요약은 기존 설정 API로 화면에서 따로 부른다.

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 911 passed

## 남은 작업
- FE-17a 과정·기수 화면.
