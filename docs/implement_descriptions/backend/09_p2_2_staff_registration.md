# 09. P2-2 운영진 최초 정보 입력

- 상태: PR 진행 중
- 관련 PR: #12
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P2 (P2-2)
- 이전 기록: [08. P2-1 인증 기반과 운영진 Google 로그인](08_p2_1_auth_google_login.md)

## 배경
P2-1에서는 운영진이 처음 Google 로그인하면 승인 대기(PENDING) 회원이 만들어진다. 사용자가 정한 흐름(decisions A11)의 두 번째 단계를 이번에 만든다. 운영진이 부서·직위·고용 형태·담당 과정/기수를 입력해 신청하는 단계다. 어드민 승인은 P3에서 만든다(A12).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `contexts/organization/domain/registration.py` | `EmployeeRegistration`(신청 애그리거트)와 `RequestedAssignment`(역할 + 과정 또는 기수). 담당은 중복 없이 20개까지, 대기 중일 때만 수정 가능. 상태와 검토 시각이 일치해야 함 |
| `contexts/organization/infrastructure/` | 모델 2개, 리포지토리(신청과 담당을 함께 저장, 담당은 통째로 교체, 최근 신청 조회) |
| `migrations/models/4_..._staff_registrations.py` | aerich 생성 + raw SQL: 회원당 PENDING 하나(부분 유니크), 담당 중복 방지(`NULLS NOT DISTINCT`), 과정·기수 중 하나만, 상태·검토 시각·반려 사유 check, enum CHECK, 기본값. downgrade 순서 수정 |
| `contexts/academy/application/catalog.py` | `AcademyCatalog`(공개 서비스): 담당으로 고를 수 있는 과정(활성)·기수(준비·진행 중, 활성 과정 소속) 조회와 검증. 리포지토리에 `list_active`, `list_by_statuses` 추가 |
| `contexts/organization/application/registration_service.py` | `StaffRegistrationService`: 선택지, 내 신청, 신청·수정. 운영진 도메인 계정만, 승인된 계정은 409, 부서·직위·담당 대상 검증 |
| `contexts/organization/presentation/` | `GET /me/staff-registration/options`, `GET·PUT /me/staff-registration` |
| `main.py` | `app.state.academy_catalog` 연결 (B10) |
| `tests/` | 도메인 규칙, DB 제약(부분 유니크·NULLS NOT DISTINCT·check), 선택지 필터, 서비스(인메모리 가짜), API(검증 오류 코드, 403·409·401) |
| `docs/database_schema_v2.dbml` | 테이블 2개와 `EmployeeRegistrationStatus` enum 추가 |

## 주요 결정
- **사용자 결정 (A11):** 담당 역할(매니저·조교)과 과정·기수는 신청자가 직접 고른다(직위와 연결하지 않음).
- 반려된 신청은 고치지 않고 새 신청을 만든다. 반려 사유와 이력이 남는다. 대기 중인 신청은 같은 행을 고친다. 회원당 PENDING 하나는 부분 유니크 인덱스로 DB에서도 막는다.
- 담당 없이 신청할 수 있다(0개). 팀장처럼 과정·기수 담당이 없는 직위가 있기 때문이다.
- 담당 대상은 활성 과정과 준비·진행 중 기수만 허용한다. 종료·보관된 기수는 선택지에 나오지 않고, 요청에 넣으면 422 `invalid_staff_target`이다.
- organization 서비스는 academy를 Protocol(`StaffTargetCatalog`)로 받는다. 구현(`AcademyCatalog`)은 `app.main`에서 연결한다. 그래서 다른 컨텍스트의 infrastructure를 import하지 않는다(B10).
- 모델 docstring은 aerich가 테이블 COMMENT로 넣는다. 그래서 다른 모델처럼 클래스 위 주석으로 바꿨다.

## 발견한 문제와 해결
- aerich downgrade가 이번에도 부모 테이블부터 지우도록 생성됐다. 참조하는 담당 테이블부터 지우도록 고쳤다.
- 리포지토리에서 `**dict[str, object]`로 엔티티를 만들면 mypy가 거부한다. 공통 `to_entity()`를 쓰고 담당·생성 시각만 따로 채우도록 바꿨다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports(10개 계약 유지), pytest **155개 통과**(통합 포함)
- 개발 DB:
  - `aerich upgrade` 성공
  - `aerich migrate` → "No changes detected"
  - `aerich downgrade -v 3` → `upgrade` 성공
- DBML 파서 검증(테이블 42개)
- 실행 중인 api + 개발 DB로 신청 흐름 전체 확인(임시 데이터 생성 후 삭제):
  - `/me` → PENDING
  - 선택지 조회
  - 신청(담당 2개)
  - 수정(담당 1개)
  - 조회

## 남은 작업
- P3: 권한(RBAC), 운영진 가입 승인·반려 API(항목 조정), 최초 어드민 CLI, 부서·직위 시드, `/me`에 역할 추가
- 프론트엔드: 최초 로그인 후 신청 화면, 대기·반려 상태 화면
