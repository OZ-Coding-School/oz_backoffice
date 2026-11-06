# 13. P3-2a 권한 판정과 require_permission 의존성

- 상태: PR 진행 중
- 관련 PR: #16
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P3 (P3-2a)
- 이전 기록: [10. P3-1 역할·권한 모델과 최고 관리자 CLI](10_p3_1_roles_super_admin_cli.md)

## 배경
P3-1에서 역할·권한 테이블과 최고 관리자 CLI를 만들었다. 이제 운영진 API가 "이 사용자가 이 기수에서 이 작업을 할 수 있는가"를 판정해야 한다. 다음 PR(P3-2b)의 가입 승인 API가 이 판정을 처음으로 쓴다. P3-2를 둘로 나눠 이번에는 판정 기반만 만든다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `contexts/access/application/permissions.py` | `PermissionChecker.has / require`, `PermissionTarget`(GLOBAL / ANY / BOOTCAMP / COHORT), `CohortDirectory` Protocol |
| `contexts/academy/application/catalog.py` | `bootcamp_id_of(cohort_id)`: 기수가 속한 과정 (BOOTCAMP 범위 역할로 기수 대상을 판정할 때) |
| `contexts/access/presentation/dependencies.py` | `get_permission_checker`(요청 단위), `require_permission(code, cohort_param= \| bootcamp_param= \| any_scope=)` |
| `tests/` | 권한 매트릭스(역할 × 범위 × 권한 15가지), 만료 역할, 없는 기수, 요청당 역할 1회 조회, API(전체·기수 범위 허용/403, 잘못된 ID 404, 승인 대기 403, 비로그인 401), 선언 오류 |

## 주요 결정 (A16)
- 역할→권한은 코드 정의(`catalog.py`)로 계산한다. DB `role_permissions`는 시드로 맞춘 사본이다. 요청마다 조인하지 않고, 코드와 DB가 어긋날 여지도 없앤다.
- 범위
  - GLOBAL: 모든 대상
  - BOOTCAMP: 그 과정과 소속 기수 전부
  - COHORT: 그 기수만. 기수 역할로 과정 단위 대상은 판정하지 않는다.
- 범위가 없는 권한(`contract.manage`: "매니저 역할이 하나라도 있으면 허용")은 `any_scope=True`로 쓴다.
- 대상 기수가 없으면 범위 역할로는 거부한다(존재 여부를 드러내지 않음). GLOBAL 역할은 통과시키고 라우터가 404를 낸다.
- 정의되지 않은 권한 코드나 범위 중복 지정은 라우터를 선언할 때(import 시점) `ValueError`로 바로 실패한다.
- 리소스 소유(본인 신청·본인 세션)는 권한 코드가 아니라 서비스에서 검사한다(plan §2.3).

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **213개 통과**(통합 포함)

## 남은 작업
- P3-2b: 운영진 가입 승인·반려 API, 담당자 배정과 `user_roles` 동기화
