# 82. 운영진 유효 권한·담당 기수 (BE-3)

- 상태: 완료 (2026-11-24 병합)
- 관련 PR: #125
- 관련 결정: `docs/decisions.md` A81, F17, F58 (A16·A17·A36)
- 이전 기록: [81. CI 변경 감지: 이전 커밋이 통과했을 때만 건너뛰기](81_ci_change_base_fix.md)

## 배경
운영진 화면(FE-14~)은 권한이 없는 모듈·메뉴·버튼을 숨기고, 상단의 '현재 기수'로 기수 단위 화면을 고른다(F3·F17). 권한표는 백엔드 코드(`access/domain/catalog.py`) 한 곳에만 있어 프론트가 계산할 수 없다. 또 지금 기수 목록 API는 `org.manage`(최고 관리자)가 있어야 해서 매니저·조교는 기수 목록을 받을 수 없다. 이 둘을 한 응답으로 준다.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `academy/application/catalog.py` | `CohortSummary`, `cohorts_in_scope(all_cohorts, bootcamp_ids, cohort_ids)`: 보관 제외, 진행 중 → 예정 → 종료 → 비활성, 최근 시작 순 |
| `access/application/staff_access.py` | `StaffAccessQueries`: 권한 코드마다 `PermissionChecker.scope_of`(판정과 같은 규칙)로 범위를 구하고, 범위를 합쳐 담당 기수를 고른다 |
| `access/presentation/me_router.py` | `GET /me/staff-access`. 운영진만(그 밖 403 `staff_only`) |
| `api/v1.py` | 라우터 등록 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 생성 타입 갱신 |

- 사용자 역할은 요청당 한 번 읽는다(체커 캐시). 기수는 상태로 한 번, 과정명은 한 번 읽어 화면 수준(수백 개)에서 거른다.

## 주요 결정 (사용자 결정, A81·F58)
- 별도 API, 담당 범위 전체(종료 포함)·진행 중 먼저.
- 운영진 Figma는 PR마다 그 화면만 다듬고, 운영진 화면은 데스크톱(1440)만 지원한다.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 907 passed (통합 테스트 포함). 통합: 범위별 기수와 순서·보관 제외. API: 최고 관리자(모든 권한·모든 기수), 기수 조교 + 과정 매니저(범위 합치기), 역할 없는 운영진(빈 응답), 수강생 403·비로그인 401
- 프론트엔드: `typecheck` 통과

- GitHub Actions (PR #125): 백엔드·프론트엔드 검사·E2E 통과
- 사용자가 병합을 확인했다(2026-11-24)

## 남은 작업
- FE-14 운영진 틀·홈 (Figma 1440 다듬기 → 구현)
