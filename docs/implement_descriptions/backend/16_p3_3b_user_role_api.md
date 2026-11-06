# 16. P3-3b 회원 역할 관리 API

- 상태: 완료 (2026-11-06 병합)
- 관련 PR: #19
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P3 (P3-3b)
- 이전 기록: [15. P3-3a 과정·기수 담당자 관리 API](15_p3_3a_staff_assignment_api.md)

## 배경
P3의 마지막 PR이다. 최고 관리자는 지금까지 CLI(구현 기록 10)로만 만들 수 있었다. 이제 최고 관리자가 다른 운영진에게 최고 관리자 권한을 주거나(임시 권한 포함) 회수하고, 회원이 가진 역할 전체를 볼 수 있게 한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `access/domain/repositories.py`, `access/infrastructure/repositories.py` | `get`, `delete`, `list_by_user`(만료 포함), `lock_effective_holders`(역할 보유자 행을 `SELECT ... FOR UPDATE`) |
| `access/application/role_admin.py` | `RoleAdministration.list_for_user / grant / revoke`. 직접 관리 역할 검사, 승인된 활성 회원 검사, 만료 시각 검사, 중복 409, 다른 회원의 역할 부여 ID 거부, 마지막 최고 관리자 보호, 감사 로그 |
| `identity/application/auth_service.py` | `UserQueries.get` |
| `access/presentation/admin_router.py` | `GET·POST /admin/users/{user_id}/roles`, `DELETE .../{user_role_id}`. 응답에 `is_effective`와 `managed_by`(direct / assignment) |
| `tests/` | 서비스(실제 DB: 부여·목록·회수, 중복, 마지막 최고 관리자, 만료된 관리자는 남은 관리자로 세지 않음, 배정 관리 역할 거부, 오류), API(부여 직후 관리 API 사용 가능 → 회수 후 403, 담당 역할은 목록에만 나오고 수정 불가, 마지막 최고 관리자 409, 404·422·401) |

## 주요 결정
- **A17:** 직접 부여·회수는 SUPER_ADMIN만 가능하다. 매니저·조교·멘토·수강생 역할은 각 원천 기능(담당자 API, 멘토 배정, 수강 등록)에서만 바꾼다. 이 API로 바꾸면 담당자 표시와 권한이 어긋나기 때문이다(D4). 목록에서는 모든 역할을 보여 주고 `managed_by`로 어디서 관리하는지 알려 준다.
- 마지막 최고 관리자(만료되지 않은)는 회수할 수 없다(409 `last_super_admin`). 관리자가 아무도 없으면 CLI로만 복구할 수 있기 때문이다. 동시에 두 관리자가 서로를 회수하는 경합은 보유자 행을 잠가 막는다. 다른 최고 관리자가 있으면 자기 역할도 회수할 수 있다.
- 만료 시각을 지정한 임시 최고 관리자 권한을 줄 수 있다. 만료된 부여는 남은 관리자 수에 넣지 않는다.
- 부여 대상은 승인된 활성 회원이어야 한다. 승인 대기 회원에게 권한을 주는 것은 가입 승인 흐름을 우회하는 것이기 때문이다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **244개 통과**
- 커밋 2개를 각각 워크트리로 꺼내 같은 검사 통과
- GitHub Actions (PR #19, run 42159728325): backend 잡 통과
- 사용자 확인: P3-3 진행 지시에 따라 CI 통과 후 병합

## 남은 작업
- P4: 조직·과정·기수 관리 API (직원 목록 포함)
