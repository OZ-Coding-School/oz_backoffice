# 06. P1-3 organization 모델

- 상태: PR 진행 중
- 관련 PR: #9
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P1 (P1-3)
- 이전 기록: [05. P1-2 academy 모델](05_p1_2_academy_models.md)

## 배경
P1의 마지막 PR이다. 부서·직위·직원과 과정·기수 담당자(운영 매니저·조교)를 만든다. 담당자는 화면 표시용이고, 권한은 P3에서 `user_roles`와 동기화한다(decisions D4).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `contexts/organization/domain/` | `Department`(이름·설명 길이, 자기 자신을 상위로 지정 금지), `EmployeePosition`(우선순위 ≥ 0), `Employee`(부서·직위 이동), `BootcampStaff`, `CohortStaff`, enum 2개, 리포지토리 Protocol |
| `contexts/organization/infrastructure/` | Tortoise 모델 5개(모든 FK는 RESTRICT), 리포지토리 구현(담당자 추가·해제·과정별·기수별·직원별 조회) |
| `migrations/models/2_..._organization_models.py` | aerich 생성 + raw SQL: 부서 자기 참조 FK, `UNIQUE (parent_id, name) NULLS NOT DISTINCT`, 자기 참조 금지 check, 고용 형태·담당 역할 enum CHECK, DB 기본값. downgrade 삭제 순서 수정 |
| `tests/unit/organization`, `tests/integration/organization` | 엔티티 규칙, 부서 트리와 상위별 이름 유일, 최상위 부서 이름 유일, 상위 부서 삭제 RESTRICT, 회원당 직원 1명, 담당자 역할별 유일, check 제약 |
| `docs/database_schema_v2.dbml` | 부서 자기 참조 금지 check, `bootcamp_staffs.bootcamp_id` 인덱스 추가 |
| `apps/backend/CLAUDE.md` | aerich 생성물에서 직접 고쳐야 하는 것(downgrade 순서, 자기 참조 FK)과 마이그레이션 검증 절차 추가 |

## 주요 결정
- `departments.parent_id`는 Tortoise 모델에서 FK가 아닌 `UUIDField`로 둔다. aerich 0.10이 자기 참조 FK를 "cyclic fk references"로 보고 마이그레이션 생성을 거부하기 때문이다. FK 제약(ON DELETE RESTRICT)은 raw SQL로 걸어 DB 무결성은 같다.
- 부서명 유일 제약은 `NULLS NOT DISTINCT`(PostgreSQL 15+) 유니크 인덱스로 둔다. 일반 유니크로는 최상위 부서(parent_id NULL)끼리 이름이 겹쳐도 막지 못한다.
- 여러 단계에 걸친 부서 순환(A → B → A)은 엔티티 하나로는 판단할 수 없다. 부서 트리를 조회하는 서비스(P4)에서 검사한다.
- 담당자 테이블은 DBML대로 `updated_at` 없이 `created_at`만 둔다(추가·해제만 하고 수정하지 않음).

## 발견한 문제와 해결
- aerich `migrate`가 자기 참조 FK에서 `ConfigurationError: Can't create schema due to cyclic fk references`로 실패했다. 위 결정대로 해결했다.
- aerich가 만든 downgrade 순서가 이번에도 FK 의존과 맞지 않아 수정했다. 하네스(백엔드 CLAUDE.md)에 주의사항으로 남겼다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports 통과, pytest **81개 통과**(통합 포함)
- 개발 DB:
  - `aerich upgrade` 성공
  - `aerich migrate` → "No changes detected"
  - `aerich downgrade -v 2` → `upgrade` 성공
  - `uid_departments_parent_name` 인덱스가 `NULLS NOT DISTINCT`로 생성됐는지 확인
- DBML 파서 검증(테이블 41개)
- GitHub Actions: PR에서 확인 후 기록

## 남은 작업
- P2: 인증 기반과 운영진 Google 로그인
