# 86. 권한 엔터티 × 조회/관리 세분화 (BE-3f)

- 상태: PR 진행 중
- 관련 PR: (작성 중)
- 관련 결정: `docs/decisions.md` A86 (A84·A83·A33)
- 이전 기록: [85. 역할별 권한 DB 판정·역할 관리 API (BE-3d)](85_role_permission_management.md) (BE-3e 역할 보유자·직접 부여 #133은 A87로 병합하지 않고 닫았다)

## 배경
FE-15d 역할·권한 시안을 보면서, 권한이 기능 묶음 단위(예: `org.manage` 하나가 부서·직위·직원·과정·HRD·기수 전부)라 역할을 세밀하게 만들 수 없다는 의견이 나왔다. 권한을 엔터티별 조회·관리로 나누고, 역할별 권한 화면도 행 = 엔터티, 칸 = 조회·관리로 바꾸기로 했다(A86).

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `access/domain/catalog.py` | `PermissionDefinition`(코드·영역·엔터티·동작·설명·전체 전용·함께 필요한 조회) 40개, `LEGACY_PERMISSIONS`(예전 14개 → 새 코드), 기본 역할 초기 묶음 |
| `access/domain/roles.py` | 관리·동기화·취소·마감은 조회와 함께(`permission_requires_read`) |
| `access/infrastructure/repositories.py`, `domain/repositories.py`, `application/roles.py` | 시드가 예전 코드를 가진 역할을 새 코드로 한 번 바꾸고 예전 코드를 지운다. 새 목록에도 있는 코드(`mentoring.request.read`)는 예전 코드가 남아 있을 때만 확장 |
| `access/application/role_catalog.py`, `presentation/role_router.py` | 권한 목록 응답에 `area`·`entity`·`action`·`requires` |
| 라우터 전부 (`academy`·`educator`·`identity`·`mentoring`·`organization`·`access`) | GET은 엔터티 조회, 그 밖은 관리(또는 동기화·취소·마감) 권한. 기수는 경로의 과정·기수 범위로 검사 |
| `identity/application/signup_review.py` | 목록·후보는 조회, 승인·반려는 관리(회원 가입 승인·계약) |
| `organization/presentation/org_router.py` | 직원 조회는 `org.employee.read` 하나로(A83의 '조직 관리 또는 담당자 배정'은 팀리드 기본 묶음의 직원 조회로 대체) |
| `apps/frontend` 메뉴·화면·테스트 | 새 권한 코드. 조회만 있으면 담당자 추가·해제, 가입 승인·반려, 운영진 검토 버튼을 숨김 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 생성 타입 갱신 |
| `docs/operations/production_notes.md` | 시드는 API를 새 버전으로 띄우기 전에, A86 배포 때 예전 코드 전환 |

- 기본 묶음: 조교 12개, 운영 매니저 22개, 팀리드 25개, 최고 관리자 40개(항상 전체). 개발 DB에 `seed-roles`를 실행해 같은 결과를 확인했다.

## 주요 결정 (사용자 결정, A86)
- 엔터티 × 조회/관리, 목록 초안 그대로(21개 엔터티), 관리는 조회 포함, 시드 CLI가 대응표로 전환, 백엔드 먼저 바꾼 뒤 FE-15d.

## 발견한 문제와 해결
- 첫 구현에서 시드가 대응표의 키를 모두 지워, 새 목록에도 있는 `mentoring.request.read`·`mentoring.request.cancel` 권한 행까지 지웠다(역할 매핑 FK 오류). 예전에만 있던 코드만 지우고, 전환은 그런 코드가 남아 있을 때 한 번만 하도록 고쳤다(전환 뒤 화면에서 끈 권한을 다시 켜지 않음). 통합 테스트로 확인했다.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 936 passed (통합 포함). 단위: 기본 묶음·대응표가 정의된 코드만 쓰고 조회를 포함, 관리만 있으면 422. 통합: 예전 코드 전환·한 번만. API: 조회만 있는 새 역할은 부서 목록 200·추가 403, 권한 목록 메타데이터
- 프론트엔드: `lint`, `format:check`, `typecheck`, `vitest` 304 passed(UTC·Asia/Seoul), `build`, Playwright E2E 39 passed

## 남은 작업
- BE-3g 직위 = 역할(A87): 직위 권한·데이터 범위, 최고 관리자 필드, 역할 테이블 정리. 이번의 '전체 범위 전용' 제한은 그때 없앤다
- FE-15d 직위·권한 화면(F63)
- 운영 배포 때 `seed-roles`를 API 시작 전에 실행
