# 23. P5-3 과정-기수 테이블로 학사 마스터 동기화

- 상태: PR 진행 중
- 관련 PR: (작성 예정)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P5 (P5-3)
- 이전 기록: [22. P5-2c 명단 동기화 관리 API](22_p5_2c_roster_sync_api.md), [18. P4-2 학사 관리 API](18_p4_2_academy_admin_api.md) (기수-HRD 일치 검증을 이번에 없앰)

## 배경
사용자가 조회할 Airtable Base와 테이블을 바꿨다. 이제 같은 Base의 두 테이블을 쓴다. 수강생 테이블은 `AIRTABLE_STUDENT_TABLE_ID`, 과정-기수 테이블은 `AIRTABLE_BOOTCAMP_TABLE_ID`다. 두 테이블을 분석한 뒤 스키마에 맞게 동기화를 수정해 달라는 요청이었다.

## 분석 (2026-11-09, 읽기 전용)
- **과정-기수 테이블 (110건, 레코드 1건 = 기수 1개)**
  - 사용하는 필드: `캠프기수`(`"헬스케어 3기"`), `과정코드`(AH·BE·FE·BD·PD·GM·IH·AL·MVP·BX·UD·CEO·FULL, 사용자가 추가), `훈련과정ID`(HRD-Net ID), `훈련과정명`, `훈련회차`, `훈련시작일`·`훈련종료일`, `과정 진행상태`(개강 전 / 훈련 중 / 취업 산정 기간 / 취업 산정 종료)
  - 그 밖에 모집·수강·취업 집계 필드가 있다. 기수가 없는 레코드는 4건이다.
  - 별칭과 과정코드는 1:1이다. 하나의 HRD 과정에 여러 운영과정이 있다(예: `…498072` 아래에 PD·BX·UD).
  - **1인창업(IH)·CEO는 기수마다 HRD 과정이 다르다.** 사용자 설명: CEO 1기는 HRD 프론트엔드 과정 9회차, IH의 한 기수는 같은 과정 16회차(실데이터상 IH 3기).
- **수강생 테이블:** 다시 시도해도 **403**(토큰 권한 또는 테이블 ID 문제)이다. 과정-기수 테이블의 `수강생 정보 시트` 링크 필드로 보면 같은 Base에 있다. 사용자 확인이 필요하다.
- 개인정보 출력 방지: 이번 조회는 허용 목록 방식으로 출력했다. 범주형 필드만 값을 출력하고, 사람 이름이 들어갈 수 있는 필드는 형태와 건수만 출력했다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `academy/application/academy_admin.py` 외 | 기수 생성·수정의 `hrd_cohort_mismatch` 검증을 없앴다(D6 보완). HRD 회차가 있는지만 확인한다 |
| `academy/domain/cohort_source.py` | 과정-기수 레코드 해석(`CohortFieldMap`, `interpret_cohort`), 진행상태 매핑, 과정코드 수식 |
| `academy/application/cohort_master_sync.py` | `CohortMasterSync.apply`: HRD 과정 → HRD 회차 → 운영과정 → 기수 순으로 만들거나 갱신한다. 대표 HRD 과정은 그 코드의 기수가 가장 많이 속한 HRD 과정이다. 운영진이 정한 INACTIVE·ARCHIVED는 유지한다. 규칙에 어긋난 레코드는 실패 목록에 남긴다 |
| `academy/application/roster_sync.py` | 실행 순서: 과정-기수 조회 → 마스터 반영(트랜잭션 1) → 수강생 조회 → 수강생 반영(트랜잭션 2). 과정·기수 범위면 그 과정코드만 조회한다. 별칭 확인은 요청 시점이 아니라 마스터 반영 후로 옮겼다 |
| `cohorts.airtable_record_id` (마이그레이션 8) | 과정-기수 레코드와 기수를 잇는 키 |
| `core/config.py`, `.env.example` | `AIRTABLE_STUDENT_TABLE_ID`, `AIRTABLE_BOOTCAMP_TABLE_ID`(이전 `AIRTABLE_TABLE_ID` 대체) |
| `academy/presentation/roster_factory.py` | 동기화 서비스 조립을 한 곳에 두고 API와 워커가 함께 쓴다 |
| `tests/` | 레코드 해석, 마스터 동기화(CEO·IH가 다른 HRD 회차 사용, 대표 HRD, 멱등, 기간·상태 갱신과 수동 상태 유지, 코드·번호로 기존 기수 연결, 잘못된 레코드), 전체 흐름(마스터 → 수강생, 과정 범위 코드 수식), API 기대값 갱신 |

## 주요 결정
- **사용자 결정 (D6 보완):** HRD 과정 하나에 운영과정이 여러 개 있고, 운영과정은 과정코드로 구분한다. 기수는 HRD 회차에 연결하며, 그 회차가 운영과정의 대표 HRD 과정과 달라도 된다.
- **A20:** 과정-기수 테이블이 학사 마스터의 원천이다. 운영과정 이름은 Airtable에 없어서 새로 만들 때 기수 별칭을 이름으로 쓴다. 관리 API로 바꿀 수 있고, 이후 동기화는 이름을 덮어쓰지 않는다.
- 기존 기수는 레코드 ID로 먼저 찾고, 없으면 (과정코드, 기수 번호)로 찾아 레코드 ID를 연결한다. 레코드 ID로 찾은 기수의 과정·번호가 바뀌었으면 자동으로 옮기지 않고 실패 목록(`cohort_record_moved`)에 남긴다.
- 마스터 반영과 수강생 반영은 트랜잭션을 나눴다. 수강생 테이블 조회가 실패해도 과정-기수 정보는 맞춰진다.

## 발견한 문제와 해결
- 수강생 테이블 403: 코드 문제가 아니다. 사용자에게 토큰 권한과 테이블 ID 확인을 요청했다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **325개 통과**
- 개발 DB:
  - `aerich upgrade` 성공
  - `aerich migrate` → "No changes detected"
  - `aerich downgrade -v 7` → `upgrade` 성공
- DBML 파서 검증(테이블 42개)
- **개발 DB 실데이터 동기화 (사용자 요청으로 데이터를 남김)**
  - 워커로 전체 동기화를 실행했다.
  - 생성 결과: HRD 과정 9, HRD 회차 106, 운영과정 13, 기수 106
  - 기수 상태: 종료 91, 진행 14, 준비 1
  - CEO 1기 → 프론트엔드 HRD(`…455720`) 9회차, IH 3기 → 같은 과정 16회차, IH 나머지 7개 기수 → `…459179`
  - 수강생 조회는 403이라 실행은 FAILED로 기록됐다. 과정-기수 데이터는 저장됐다.

## 남은 작업
- 수강생 테이블 접근 문제 해결 후, 수강생 테이블의 실제 필드 구조를 확인해 매핑을 맞춘다. 수강생이 기수 레코드를 링크로 참조하면 라벨 대신 `cohorts.airtable_record_id`로 매핑한다.
- 개발 환경 스케줄러가 매시 전체 동기화를 실행한다. 403이 해결될 때까지 실행 이력은 FAILED로 쌓이지만, 과정-기수 데이터는 계속 맞춰진다.
