# 61. 조교 담당 기수는 비어 있는 기수만

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A63 (A62 보완)
- 이전 기록: [60. 조직 구조: 부서·팀과 직위 담당 방식](60_org_teams.md)

## 배경
FE-1c 화면(Figma)을 확인하던 중 사용자가 조교 신청 방식을 정했다. 조교 직위는 과정을 먼저 고르고 그다음 기수를 고른다. 이때 **이미 조교가 배정된 기수는 보여 주지 않는다.**

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `organization/domain/repositories.py`, `infrastructure/repositories.py` | `CohortStaffRepository.cohort_ids_with_role(role)`: 그 역할의 담당자가 있는 기수 |
| `organization/domain/registration.py` | `check_assignment_scope`에 `assisted_cohort_ids` 추가. COHORT 직위는 이미 조교가 있는 기수를 고를 수 없다 |
| `organization/application/registration_service.py` | 신청 선택지 `cohorts`에서 승인된 조교가 있는 기수를 뺀다. 신청할 때 그 기수를 고르면 422 `invalid_staff_assignment` |
| `organization/presentation/schemas.py`, `dependencies.py` | `cohorts` 설명, 리포지토리 조립 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 다시 만들었다(F19) |

## 주요 결정 (사용자 결정, A63)
- "조교가 있는 기수"는 승인된 담당(`cohort_staffs`의 ASSISTANT)만 본다. 승인 대기 신청은 고려하지 않는다.
- 신청할 때 서버도 거부한다. 승인 조정은 A62대로 자유다.
- 백엔드 PR을 먼저 병합하고 FE-1c(#78)를 고친다.

## 검증
- 단위
  - 규칙: 조교 있는 기수 거부
  - 신청 서비스: 선택지에서 빠지고 신청하면 거부된다. 운영 매니저가 담당인 기수는 그대로 보인다
- 통합: `cohort_ids_with_role` 조회
- 로컬 검사 (compose `api`): ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 864 passed.

## 남은 작업
- FE-1c(#78): 부서 → 팀 → 직위 → 담당 단계 노출, 조교는 과정 → 기수 선택
