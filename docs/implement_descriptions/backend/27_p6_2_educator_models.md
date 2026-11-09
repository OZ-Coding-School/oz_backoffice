# 27. P6-2 멘토·강사·계약·계약서 모델

- 상태: PR 진행 중
- 관련 PR: #30
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P6 (P6-2)
- 이전 기록: [26. P6-1 S3 어댑터](26_p6_1_s3_adapter.md)

## 배경
P6의 두 번째 PR이다. 교육 인력(멘토·강사) 프로필과 계약·계약서 테이블을 만든다. 업로드·계약 API(P6-3)와 수동 연결·멘토 프로필 API(P6-4)가 이 테이블을 쓴다. P1 때 educator 컨텍스트는 빈 모델 모듈만 있었다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `educator/domain/enums.py` | `EducatorType`(MENTOR/INSTRUCTOR), `ContractStatus`(DRAFT/ACTIVE/ENDED/TERMINATED), `DisplayNamePreference`(NAME/NICKNAME) |
| `educator/infrastructure/models.py` | `MentorModel`, `InstructorModel`, `ContractFileModel`, `EducatorContractModel` |
| `migrations/models/9_…_educator_models.py` | 테이블 4개 + raw SQL(DB 기본값, enum CHECK, DBML check 제약) |
| `docs/database_schema_v2.dbml` | 프로필 컬럼 추가, `contract_file_id` NULL 허용, 새 check, `DisplayNamePreference` enum |
| `tests/integration/educator/test_educator_models.py` | DB 기본값과 제약 위반 시 실제로 실패하는지 확인 |

- DB 제약:
  - `check_mentor_display_nickname`, `check_instructor_display_nickname`: NICKNAME은 닉네임이 있을 때만 허용
  - `check_contract_period`: 시작일 ≤ 종료일
  - `check_contract_email_lowercase`: 이메일은 소문자로 저장
  - `check_contract_educator_type`: 계약 유형과 연결 컬럼이 일치(멘토 계약에 강사 연결 불가, 반대도 같음)
  - `check_contract_file_required`: DRAFT가 아니면 계약서가 있어야 함
  - enum 값 CHECK
- 유니크: 회원당 멘토·강사 프로필 1개(`user_id`), 계약서 1개는 계약 1건에만 연결(`contract_file_id`), 계약서 객체 키(`storage_key`)
- 도메인 엔티티와 리포지토리는 이 테이블을 쓰는 유스케이스와 함께 P6-3·P6-4에서 만든다.

## 주요 결정 (사용자 결정)
- **A22 멘토·강사 프로필:** 기존 스키마에 한 줄 소개 `headline`(varchar 100)과 표시 이름 선택 `display_name_preference`(기본 NAME)를 더했다. NICKNAME은 닉네임이 있을 때만 고를 수 있다. 이는 기존 mentor 서비스의 동작과 같다. 소개는 마크다운을 허용하는 text다. 기존 서비스의 서브 사진(최대 6장)은 두지 않는다. 강사도 멘토와 같은 구조로 둔다.
- **A23 계약서 없는 DRAFT:** 계약 정보를 먼저 등록하고 서명본을 나중에 올릴 수 있도록 `contract_file_id`를 NULL 허용으로 바꿨다. DRAFT가 아닌 상태는 계약서가 필요하다.

## 발견한 문제와 해결
- 마이그레이션 왕복 검증 중 `aerich downgrade -v 8 -d`를 실행했다. `-d`는 마이그레이션 파일까지 지우는 옵션이다. 확인 프롬프트에서 멈춘 상태로 중단해 파일과 DB는 바뀌지 않았다. 이후 `--yes`로 다시 실행했다. 작업 하네스의 검증 절차에는 `-d`를 쓰지 않는다.

## 검증
- DBML 파서(`@dbml/core` 11) 검증: 테이블 42개
- 개발 DB: `aerich upgrade` → `aerich migrate`("No changes detected") → `aerich downgrade -v 8 --yes` → `aerich upgrade`
- 통합 테스트 11개: DB 기본값(NAME, is_active, DRAFT, now()), 닉네임 check, 회원당 프로필 1개, DRAFT 계약서 생략과 ACTIVE 계약서 필수, 계약서 1:1, 기간·이메일 check, 유형-연결 check
- `docker compose exec api`에서 ruff, ruff format, mypy, mypy tests, lint-imports(10 kept), pytest 350 passed

## 남은 작업
- P6-3 계약서 업로드·계약 CRUD·상태 전이 API
- P6-4 계약 수동 연결·멘토 프로필 API
