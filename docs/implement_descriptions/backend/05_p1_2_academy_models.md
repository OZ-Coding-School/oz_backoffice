# 05. P1-2 academy 모델

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P1 (P1-2)
- 이전 기록: [03. P1-1 identity·audit 모델과 첫 마이그레이션](03_p1_1_identity_audit_models.md)

## 배경
과정·기수·수강생은 모든 멘토링 기능이 참조하는 공통 마스터다. organization의 담당자 테이블도 이 테이블들을 FK로 참조하므로, 계획의 P1-2와 P1-3 순서를 바꿔 academy를 먼저 만든다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `src/app/shared/normalization.py` | 이름·휴대폰 정규화를 identity에서 공유 커널로 이동. 회원·명단·계약이 같은 규칙으로 정규화해야 자동 매칭(A6)이 맞는다 |
| `src/app/core/persistence.py` | `TortoiseRepository` 베이스: 엔티티와 모델의 필드 이름이 같을 때 add / save / get 변환을 공통 처리. save는 `updated_at`(auto_now)이 적용되도록 `Model.save()`를 쓴다 |
| `contexts/academy/domain/` | 엔티티 7개(HRD 과정·회차, 운영과정, 기수, 수강 등록, 수강생 명단, 명단 동기화 실행), enum 9개, 리포지토리 Protocol 7개 |
| `contexts/academy/infrastructure/` | Tortoise 모델 7개(마스터 FK는 RESTRICT, 명단의 연결 수강생은 SET NULL), 리포지토리 구현 |
| `migrations/models/1_..._academy_models.py` | aerich 생성 + raw SQL: DB 기본값, check(HRD 회차·기수·수강 기간, 동기화 범위 일관성, 휴대폰 형식), enum 값 CHECK. downgrade의 테이블 삭제 순서를 FK 의존에 맞게 수정 |
| `tests/factories/academy.py` | 명단 빌더, HRD 과정 → 회차 → 운영과정 → 기수 생성 헬퍼 |
| `tests/unit/academy`, `tests/integration/academy` | 엔티티 규칙, 리포지토리 왕복, 유니크(기수 번호, 회원×기수), 재수강 허용, 매칭 후보 조회, DB check 제약 |
| `docs/database_schema_v2.dbml` | 마이그레이션에 넣은 check 중 DBML에 없던 4개 추가: `users` 휴대폰 형식(P1-1), HRD 회차 기간, 수강 기간, 명단 휴대폰 형식 |

### 도메인 규칙
- `Bootcamp.code`: 대문자 영문·숫자
- `Cohort`: 기수 번호 1 이상, 시작일 ≤ 종료일
- `Student`:
  - `end()`는 수강 중일 때만 가능하다
  - 종료 상태를 지정해야 하고, 종료일 ≥ 등록일이어야 한다
  - 다른 기수 재수강은 허용한다 (회원×기수 유일)
- `StudentRoster`: 이름·휴대폰·이메일 정규화. `match()`는 한 번만 가능하다
- `RosterSyncRun`: 범위(ALL / BOOTCAMP / COHORT)와 대상 과정·기수의 일관성, 실행 중일 때만 성공·실패로 종료
- 가입 매칭 후보 조회(`find_unmatched_by_name_and_phone`): 기수가 매핑돼 있고, 원천에 존재하며, 아직 연결되지 않은 명단만 대상으로 한다

## 주요 결정
- P1-2와 P1-3의 순서를 바꿨다. organization의 담당자 테이블이 academy 테이블을 FK로 참조하기 때문이다.
- 운영과정과 HRD 회차가 같은 HRD 과정을 가리키는지는 두 애그리거트를 조회하는 서비스(P4)에서 검증한다. DB 제약으로 표현하려면 비정규화가 필요해 하지 않았다.
- 마스터 데이터 FK는 RESTRICT로 둔다. 삭제 대신 비활성·보관 상태로 관리한다.

## 발견한 문제와 해결
- aerich가 만든 downgrade가 참조되는 테이블(`hrd_net_bootcamp_cohorts`)을 먼저 지워 실패하는 순서였다. 참조하는 쪽부터 지우도록 고치고, 개발 DB에서 downgrade → upgrade를 실제로 실행해 확인했다.
- 컨테이너 시간대(UTC) 때문에 마이그레이션 파일명 시각이 첫 파일(KST)과 다르다. aerich는 앞 번호(0, 1)로 순서를 정하므로 영향은 없다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports 통과, pytest **70개 통과**(통합 포함)
- 개발 DB:
  - `aerich upgrade` 성공
  - `aerich migrate` → "No changes detected" (모델과 마이그레이션 일치)
  - `aerich downgrade -v 1` → `upgrade` 성공
  - check 제약 19개 적용 확인
- DBML 파서 검증(테이블 41개)
- GitHub Actions: PR에서 확인 후 기록

## 남은 작업
- P1-3 organization (부서, 직위, 직원, 과정·기수 담당자)
