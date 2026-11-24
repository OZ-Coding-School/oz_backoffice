# 84. 직원 목록 검색·팀 필터·담당 (BE-3c)

- 상태: 완료 (2026-11-24 병합)
- 관련 PR: #130
- 관련 결정: `docs/decisions.md` A83, F62 (A17·A36·A62)
- 이전 기록: [83. 가입 수동 승인 후보 (BE-3b)](83_approval_candidates.md)

## 배경
FE-15c 직원·담당자 화면은 직원마다 담당 과정·기수를 보여 주고, 담당자를 추가할 때 이름으로 직원을 찾는다. 지금 직원 목록은 담당을 주지 않고 부서 필터만 있으며, `org.manage`(최고 관리자)만 볼 수 있다. 그래서 담당자를 배정하는 팀리드(`staff.assign`)가 직원을 찾을 수 없다(A83).

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `organization/domain/repositories.py`, `infrastructure/repositories.py` | 직원 `list_page`에 `team_id`·`query`(회원 이름·이메일). 과정·기수 담당자 `list_by_employees` |
| `organization/application/org_service.py` | `list_employees`에 팀·검색어 |
| `organization/presentation/org_router.py` | 목록·단건 조회 권한을 `org.manage` 또는 `staff.assign`(전체)로 넓힘(`require_employee_viewer`), `q`·`team_id`, 응답 `assignments` |
| `academy/application/catalog.py` | `bootcamp_names` |
| `tests/fakes/organization.py` | 기수 담당자 가짜에 `list_by_employees` |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 생성 타입 갱신 |

- 담당은 직원 묶음 단위로 과정 담당자·기수 담당자를 한 번씩 읽고, 이름도 묶어 읽는다.

## 주요 결정 (사용자 결정, A83·F62)
- 직원·담당자 한 메뉴에 탭 두 개, 백엔드 보완 먼저, 조회는 `staff.assign`도 허용.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 910 passed (통합 포함). API: 이름·이메일 검색, 팀 필터, 과정·기수 담당, 팀리드는 조회 200·수정 403
- 프론트엔드: `typecheck` 통과

- GitHub Actions (PR #130): 백엔드·프론트엔드 검사·E2E 통과
- 사용자가 병합을 확인했다(2026-11-24)

## 남은 작업
- FE-15c 직원·담당자 화면
