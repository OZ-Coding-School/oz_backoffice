# 18. P4-2 학사(HRD 과정·회차, 운영과정, 기수) 관리 API

- 상태: PR 진행 중
- 관련 PR: (작성 예정)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P4 (P4-2)
- 이전 기록: [17. P4-1 조직(부서·직위·직원) 관리 API](17_p4_1_organization_admin_api.md)

## 배경
P4의 두 번째 PR이다. 최고 관리자(`org.manage`)가 HRD-Net 과정·회차, 운영과정, 기수를 직접 관리하게 한다. 이 데이터는 운영진 가입 신청의 담당 선택지, 담당자 배정, Airtable 명단 동기화(P5)의 기수 매핑, 멘토링 전반의 기준이 된다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `academy/domain/repositories.py`, `academy/infrastructure/repositories.py` | HRD 과정(HRD-Net ID·전체), HRD 회차(번호·과정별), 운영과정(이름·전체) 조회, 공통 `delete` |
| `academy/application/academy_admin.py` | `AcademyAdminService`. 수정은 `dataclasses.replace`로 엔티티를 다시 만들어 생성과 같은 검증을 거친다. 기수의 HRD 회차 ↔ 운영과정 HRD 과정 일치를 검사한다. 유일 조건은 먼저 검사해 409, 수정 가능한 필드는 화이트리스트로 제한한다. 모든 변경에 감사 로그(전후, 날짜·enum은 문자열) |
| `academy/presentation/admin_router.py` | HRD 과정·회차, 운영과정, 기수의 목록·생성·조회·PATCH·삭제. 응답은 엔티티에서 `from_attributes`로 만든다 |
| `tests/` | 조회·삭제(`in_use`), 서비스(실제 DB: 전체 계층·감사 로그 전후값, 기수 번호 중복·기간 역전·HRD 회차 불일치·소속 변경 금지, 유일 조건, 삭제 보호), API(계층 CRUD, null로 값 비우기, 비활성 목록, 검증 오류 코드 4종, 디스코드 ID 형식, 권한 403·401) |

## 주요 결정
- **바꿀 수 없는 소속:** HRD 회차의 HRD 과정, 운영과정의 HRD 과정, 기수의 운영과정은 수정할 수 없다(422 `field_not_updatable`). 이미 연결된 기수·수강생·담당자와의 일관성을 깨지 않기 위해서다. 잘못 만들었으면 새로 만든다(참조가 없으면 삭제 가능).
- 기수의 HRD 회차는 바꿀 수 있다. 다만 같은 HRD 과정의 회차여야 한다(생성과 같은 검사).
- 운영을 멈출 때는 삭제하지 않는다. 운영과정은 `is_active=false`, 기수는 상태(`ENDED`·`ARCHIVED`)로 바꾼다. 삭제는 참조가 없을 때만 된다(409 `in_use`).
- PATCH의 `null` 처리: 비울 수 있는 필드(HRD-Net ID, 날짜, 금액, 디스코드 ID 등)는 `null`로 비운다. 비울 수 없는 필드(이름, 코드, 상태, 기간 등)에 보낸 `null`은 무시한다.
- 운영과정 목록은 기본이 활성 과정만이고, `include_inactive=true`면 전체를 준다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **262개 통과**

## 남은 작업
- P5: Airtable 수강생 명단 동기화 (Airtable 접근 정보와 필드 구조 필요)
