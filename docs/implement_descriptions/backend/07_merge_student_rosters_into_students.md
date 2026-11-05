# 07. 수강생 명단(student_rosters)을 students에 합침

- 상태: 완료 (2026-11-05 병합)
- 관련 PR: #10
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P1(스키마), P5, P7
- 이전 기록: [05. P1-2 academy 모델](05_p1_2_academy_models.md) (명단 테이블을 처음 만든 기록)

## 배경
P1-2에서 Airtable 명단 사본(`student_rosters`)과 수강 등록(`students`)을 따로 만들었다. 이 구조에서는 수강생이 가입할 때 명단과 대조해 `students`를 새로 만들고 `matched_student_id`로 잇는다. 그런데 명단 레코드 1건이 곧 기수 등록 1건이라 두 테이블이 같은 사실을 중복해서 담는다. 사용자가 "student_rosters 대신 students에 user FK를 null로 두면 어떠냐"고 제안했고, 합치기로 했다(decisions A10).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `contexts/academy/domain/entities.py` | `StudentRoster` 삭제. `Student`에 Airtable 원천 필드(`airtable_record_id`, `name`, `phone_number`, `email`, `source_fields`, `synced_at`, `is_removed_in_source`)를 추가하고 `user_id`를 선택값으로 바꿈. `claim()`(회원 연결, 한 번만), `apply_source()`(동기화 값 반영, 백오피스 수강 상태는 유지), `mark_removed_in_source()` 추가. `RosterSyncRun.succeed()`가 매핑 실패 레코드 목록(`unmapped_records`)을 받아 건수를 계산 |
| `contexts/academy/domain/repositories.py` | `StudentRosterRepository` 삭제. `StudentRepository`에 `get_by_record_id`, `find_claimable_by_name_and_phone`(수강 중·원천 존재·미가입) 추가 |
| `contexts/academy/infrastructure/` | `StudentModel` 컬럼 추가, `user` FK nullable, (이름, 휴대폰) 인덱스. `StudentRosterModel` 삭제. `RosterSyncRunModel.unmapped_records`(jsonb) 추가. 리포지토리 구현 갱신 |
| `migrations/models/3_..._merge_student_rosters.py` | aerich 생성 + raw SQL: `check_students_phone_number`, `unmapped_records` 기본값 `'[]'`. downgrade에서 `student_rosters`를 1번 마이그레이션 정의(제약 포함)대로 다시 만듦 |
| `tests/` | `make_roster` → `make_student`. 단위: 정규화, claim 1회, apply_source가 수강 상태를 덮어쓰지 않음. 통합: 미가입 수강생 여러 명 저장, `airtable_record_id` 유일, 매칭 후보 필터, `unmapped_records` 왕복, 휴대폰 check |
| `docs/` | DBML(`student_rosters` 삭제, `students`·`roster_sync_runs` 변경), decisions A10 추가와 A5 문구 수정, 계획서 P1·P5·P7 갱신 |

## 주요 결정
- **사용자 결정:** 별도 명단 테이블을 두지 않고 `students`에 합친다. 가입 전에는 `user_id`가 NULL이다. 기수 매핑에 실패한 레코드는 `roster_sync_runs.unmapped_records`(jsonb)에 남긴다. 멘토링 등 기능은 가입한 수강생만 대상으로 한다 (A10).
- 필드 원천을 나눈다. 이름·휴대폰·이메일·HRD 상태는 Airtable이 원천이라 `apply_source()`로만 바꾼다. 수강 상태·종료일·사유는 백오피스가 관리하므로 동기화가 덮어쓰지 않는다.
- `airtable_record_id`는 nullable unique다. 운영진이 Airtable 없이 직접 등록한 수강생도 둘 수 있게 했다. PostgreSQL unique는 NULL끼리 겹쳐도 허용한다.
- (회원, 기수) 유니크는 그대로 둔다. `user_id`가 NULL인 행끼리는 겹쳐도 되므로, 가입 전 수강생 여러 명이 같은 기수에 있을 수 있다.
- `students.name`은 NOT NULL로 추가한다. P5 동기화 전이라 운영·개발 DB 모두 `students`가 비어 있어 기본값 없이 추가해도 된다.

## 발견한 문제와 해결
- aerich가 만든 `unmapped_records` 컬럼은 `NOT NULL`에 기본값이 없어, 기존 실행 이력이 있으면 실패한다. `DEFAULT '[]'::jsonb`를 넣었다.
- aerich downgrade는 삭제된 `student_rosters`를 되살리지 않는다. 1번 마이그레이션의 정의로 다시 만들도록 직접 썼다. 가입 전 수강생(`user_id` NULL)이 있으면 downgrade의 `SET NOT NULL`이 실패한다. 명단 데이터는 되돌리지 않는다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports 통과, pytest **84개 통과**(통합 포함)
- 개발 DB:
  - `aerich upgrade` 성공
  - `aerich migrate` → "No changes detected"
  - `aerich downgrade -v 2` → `upgrade` 성공
- DBML 파서 검증(테이블 40개)
- 코드 커밋을 워크트리로 꺼내 ruff·format·mypy·lint-imports·pytest 통과 확인
- GitHub Actions (PR #10, run 41994900163): backend 잡 통과
- 사용자 확인: 합치는 안("합침")을 선택했고, 작업 지시에 따라 CI 통과 후 병합

## 남은 작업
- P2: 인증 기반과 운영진 Google 로그인
- P5에서 Airtable 레코드의 기수가 바뀐 경우 처리 확정 (계획서에는 실패 목록에 남기고 운영진이 기수 이동으로 처리하는 안으로 적어 둠)
