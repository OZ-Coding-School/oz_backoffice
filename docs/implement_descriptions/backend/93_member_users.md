# 93. 전체 회원 API (BE-3m)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #146
- 관련 결정: `docs/decisions.md` A94 (A88)
- 이전 기록: [92. 부서·팀·직위 영향 조회 (BE-3l)](92_org_impact.md)

## 배경
회원 관리 모듈의 '전체 회원'(A88·F64)은 역할과 상관없이 회원 정보를 보고 계정을 비활성화한다. 승인된 계정만 보이고, 비활성화하면 로그인을 막고 로그인 중인 세션도 끊으며, 다시 활성화할 수 있다(A94).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `access/domain/catalog.py` | `member.user.read`·`member.user.manage`('회원 관리', 기수에 속하지 않음). 권한 42개 |
| `identity/domain/repositories.py`, `infrastructure/repositories.py` | `search_approved`(승인·탈퇴 제외, 종류·이름/이메일/휴대폰·활성 여부, 승인 최신순), `count_approved_by_type` |
| `identity/domain/entities.py` | `User.activate()`(승인 계정만) |
| `identity/application/member_admin.py` | `MemberAdministration`: 검색(종류별 수 포함), 상세(연결 정보 + 이력), 비활성화(자기 자신·마지막 최고 관리자 409, 감사 기록 후 커밋 뒤 refresh 토큰 모두 폐기), 활성화. 연결 정보·감사 조회·세션 폐기는 포트 |
| `audit/application/queries.py` | `AuditQueries.list_for_target`(대상·동작으로 거름) |
| `app/composition/member_links.py` | `MemberLinksComposer`: 수강생은 수강 기수·상태, 멘토는 배정 기수(활성 여부)·계약 수, 운영진은 부서·팀·직위. 컨텍스트끼리 내부를 import하지 않도록 조합 모듈에 둠 |
| `identity/presentation/member_router.py` | `GET /admin/users`(`counts`), `GET /admin/users/{id}`, `POST …/deactivate`(사유 1~300자), `POST …/activate`(사유 선택) |
| `main.py`, `api/v1.py` | `member_links`·`audit_queries` 배선, 라우터 등록 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

- access 토큰은 요청마다 `can_login`을 확인하므로 비활성화 즉시 막히고, refresh 토큰도 폐기해 다시 받을 수 없다.

## 주요 결정 (사용자 결정, A94)
- 승인된 계정만, 비활성화는 로그인 막기 + 세션 끊기 + 되살리기, 상세는 기본 정보 + 종류별 연결 정보.

## 발견한 문제와 해결
- 권한 개수를 고정한 테스트 두 곳을 42개로 고침.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과, `pytest` 897 passed. 새 테스트: 승인 계정만·종류 필터·검색·`counts`, 종류별 연결 정보, 비활성화(사유 필수, 이력, 로그인 중인 access 401 `account_disabled`, 비활성 필터) → 활성화(이력, 다시 로그인), 자기 자신·마지막 최고 관리자 409, 조회 권한만이면 비활성화 403
- 프론트엔드: `lint`, `typecheck` 통과
- GitHub Actions (PR #146): 백엔드·프론트엔드 검사와 E2E 통과

## 남은 작업
- FE-15i 회원 관리 > 전체 회원
