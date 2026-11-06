# 14. P3-2b 운영진 가입 신청 승인·반려

- 상태: 완료 (2026-11-06 병합)
- 관련 PR: #17
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P3 (P3-2b)
- 이전 기록: [13. P3-2a 권한 판정과 require_permission 의존성](13_p3_2a_permission_checks.md), [09. P2-2 운영진 최초 정보 입력](09_p2_2_staff_registration.md)

## 배경
운영진 가입 흐름(decisions A11)의 마지막 단계다. 최고 관리자가 신청 항목(부서·직위·고용 형태·담당)을 조정해 승인하면 운영진이 백오피스를 쓸 수 있게 된다. 반려하면 사유가 남고 신청자는 다시 신청할 수 있다. 담당자 배정과 권한(`user_roles`)은 같은 트랜잭션에서 맞춘다(D4).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `organization/domain/registration.py` | `approve(now, 조정 항목)`, `reject(now, reason)`(1~300자). 대기 중일 때만 가능 |
| `organization/domain/entities.py` | `Employee.change_employment_type` |
| `organization/infrastructure/repositories.py` | `list_by_status`(오래된 신청부터, 페이지, 전체 건수) |
| `organization/application/review_service.py` | `StaffRegistrationReviewService`. 승인은 한 트랜잭션에서 처리한다: 신청 승인 → 직원 생성·갱신 → 과정·기수 담당자 추가(있으면 건너뜀) → 역할 부여 → 회원 승인 → 감사 로그(조정 전후). 반려는 신청 반려 → 승인 대기 회원 REJECTED → 감사 로그 |
| `organization/application/registration_service.py` | 부서·직위·담당 검증을 `RegistrationChoiceValidator`로 분리해 신청과 승인이 함께 쓴다 |
| `identity/application/` | `UserAdministration.approve / mark_rejected`, `UserQueries.get_many`(목록 신청자 일괄 조회), `UserRepository.list_by_ids` |
| `organization/presentation/admin_router.py` | `GET /admin/staff-registrations`(목록), `GET /{id}`, `POST /{id}/approve`(조정 본문 선택), `POST /{id}/reject`. 권한 `role.assign`(전체 범위) |
| `main.py` | `app.state.role_assignments`, `user_admin`, `audit_recorder` 연결 (B10) |
| `tests/` | 도메인(승인 조정·반려 사유), 목록 페이지, 서비스(실제 DB: 직원·담당자·역할·회원·감사 로그, 조정, 재승인 시 중복 없음, 검증 실패 시 전체 롤백, 반려, 승인된 회원 유지, 오류), API(목록, 조정 승인 후 신청자 `/me`에 역할, 본문 없는 승인, 반려 사유 노출, 404·422, 조교 403·승인 대기 403·비로그인 401) |

## 주요 결정
- 역할 매핑: 담당 역할 MANAGER → `COHORT_MANAGER`, ASSISTANT → `COHORT_ASSISTANT`. 범위는 담당 대상(과정이면 BOOTCAMP, 기수면 COHORT)이다.
- 승인 본문의 항목은 모두 선택이다. 보내지 않은 항목은 신청값을 쓴다. `assignments`를 보내면 담당 목록 전체를 그 값으로 바꾼다(빈 배열이면 담당 없음). 감사 로그에는 조정 전(before)과 승인된 값(after)을 남긴다.
- 같은 회원이 다시 승인되면 직원 정보는 갱신하고, 이미 있는 담당자·역할은 건너뛴다. 이전 승인에만 있던 담당을 회수하는 일은 담당자 관리 API(P3-3)에서 한다.
- 반려할 때 이미 승인된 회원(예: CLI로 만든 최고 관리자)은 승인 상태를 유지한다.
- 대기 중이 아닌 신청을 다시 승인·반려하면 422 `registration_not_pending`을 돌려준다.
- 서비스 테스트는 인메모리 가짜 대신 실제 DB로 썼다. 여러 컨텍스트에 걸쳐 쓰는 결과(직원·담당자·역할·회원·감사 로그)가 한 트랜잭션으로 저장·롤백되는지가 핵심이기 때문이다(구현 기록 12 이후 DB 테스트 비용이 작다).

## 발견한 문제와 해결
- 테스트 이메일을 `new_id().hex[:8]`로 만들면 uuid7 앞자리(생성 시각)가 같은 밀리초에 겹쳐 유일 제약 위반이 났다. 끝자리(무작위)를 쓰도록 바꿨고, 같은 문제가 있던 기존 organization 테스트도 별도 `test:` 커밋으로 고쳤다.
- 서비스 메서드 이름을 `list`로 지었더니 클래스 안의 `list[...]` 타입 표기를 가려 mypy 오류가 났다. `list_by_status`로 바꿨다.
- 구현 기록 13의 CI run 번호가 비어 있어(체크 등록 전 조회) 이번 PR에서 보완했다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **229개 통과**
- 커밋 4개를 각각 워크트리로 꺼내 같은 검사 통과
- GitHub Actions (PR #17, run 42156006606): backend 잡 통과
- 사용자 확인: P3-2 진행 지시에 따라 CI 통과 후 병합

## 남은 작업
- P3-3: 과정·기수 담당자 관리 API(배정·해제와 `user_roles` 동기화), 회원 역할 관리 API
