# 25. P5-4 수강생 테이블 실구조 확인과 레코드 링크 매핑

- 상태: 완료 (2026-11-09 병합)
- 관련 PR: #28
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P5 (P5-4)
- 이전 기록: [23. P5-3 과정-기수 테이블로 학사 마스터 동기화](23_p5_3_cohort_master_sync.md), [24. 워커 반복 종료 수정](24_fix_worker_redis_socket_timeout.md)

## 배경
기록 23 시점에는 수강생 테이블 조회가 403이었다. 사용자가 `AIRTABLE_STUDENT_TABLE_ID`가 잘못돼 있었다며 고쳤다. 이제 실제 구조를 확인하고 수강생이 기수에 정확히 매핑되도록 동기화를 맞춘다. 끝나면 실행 중인 개발 DB에 실데이터를 동기화해 사용자가 직접 확인할 수 있게 한다.

## 분석 (2026-11-09, 읽기 전용)
- 레코드는 4,437건이다.
- 사용하는 필드: `이름`, `전화번호`, `이메일`, `기수`(lookup, 비어 있는 레코드 54건), `상태`, `HRD상태`, `중도탈락일`, `훈련종료일`, **`취업운영시트 link`**.
- **`취업운영시트 link`는 과정-기수 테이블 레코드를 가리킨다.** 값이 과정-기수 테이블 레코드 ID와 100% 일치한다. 기수 라벨보다 정확하므로(별칭 설정·라벨 형식과 무관) 기본 매핑 키로 쓴다.
- `중복데이터 여부`(1,945건이 True)는 의미가 확인되지 않아 쓰지 않는다.
- 개인정보 출력 방지: 기록 23과 같이 허용 목록 방식으로 출력했다. 결과 보고에는 집계만 쓴다.

## 구현 내용

| 경로 | 변경 |
| --- | --- |
| `academy/domain/roster.py` | `RosterFieldMap.cohort_link`(`취업운영시트 link`)를 조회 필드에 추가. `RosterRecord.cohort_record_id`를 추가하고 `cohort`(라벨)는 선택으로 바꿈. 링크도 라벨도 없을 때만 대상에서 제외한다 |
| `academy/application/roster_sync.py` | 기수 찾기: 링크 → `cohorts.airtable_record_id`가 먼저, 링크가 없으면 라벨(별칭 → 운영과정 → 번호). 전체 동기화는 수식 없이 테이블 전체를 읽는다(`_Scope.is_all`). 과정·기수 범위에서는 범위 밖 기수에 링크된 레코드를 건너뛴다. 전체 범위에서는 `cohort_not_found`로 남긴다 |
| `tests/fakes/roster.py`, `tests/unit/academy/test_roster.py`, `tests/integration/academy/test_roster_sync.py` | 수식 없음(전체) 처리, 링크로 매핑, 라벨 없이 링크만 있는 레코드 테스트 |

## 주요 결정
- **A21 (decisions.md):** 기수는 레코드 링크가 우선이고, 라벨은 대체 수단이다. 전체 동기화는 수강생 테이블 전체를 읽는다.
- 과정·기수 범위 동기화의 조회 수식은 라벨(`기수`) 기준을 유지한다. 링크 필드를 수식에서 쓰면 링크된 레코드의 기본 필드 값이 나와 레코드 ID로 거를 수 없다. 범위 동기화는 수동 보조 수단이고, 매시 전체 동기화가 모든 레코드를 맞춘다.

## 발견한 문제와 해결
- 실데이터 동기화를 워커에 보냈더니 워커 프로세스가 5초마다 죽었다. 별도 PR #27(기록 24)로 고친 뒤 이 브랜치를 rebase했다.
- **미매핑 54건:** 모두 같은 과정-기수 레코드에 링크돼 있다. 그 레코드는 PD(`…498072`) 19회차, 2026-11-19 개강, `개강 전` 상태다. Airtable에서 `캠프기수`·`과정코드`가 비어 있어 마스터 동기화가 기수를 만들지 않았다. 데이터 입력 대기 상태다. Airtable에 값이 채워지면 다음 주기 동기화에서 자동으로 매핑된다.

## 검증
- `docker compose exec api`에서 ruff, ruff format, mypy, mypy tests, lint-imports(10 kept), pytest 328 passed (develop rebase 후)
- **개발 DB 실데이터 동기화** (워커, `SCHEDULED`/`ALL`, 14초): 조회 4,437, 반영 4,383, 원천 삭제 0, 미매핑 54(`cohort_not_found`)
  - 운영과정 13개, 기수 104개에 수강생이 들어갔다. 많은 순으로 BD 834, PD 670, GM 559, BE 496, FE 471, AL 375, AH 366, IH 226, BX 177, UD 106, MVP 56, CEO 31, FULL 16명이다.
  - 수강 상태: COMPLETED 2,611, DROPPED 1,144, ENROLLED 510, EARLY_EMPLOYED 118
  - HRD 상태 `UNKNOWN`은 407건이다. Airtable `HRD상태`가 비어 있는 경우가 277건, `확인필요`가 130건이다. 둘 다 원천 값 그대로라 UNKNOWN이 맞다.
  - 전화번호 없음 564건, 이메일 없음 1,028건. 회원 연결(`user_id`) 0건(가입 기능은 P7).
- GitHub Actions (PR #28, run 42589351702): backend 잡 통과
- 개발 DB 데이터는 사용자 확인용으로 그대로 둔다.

## 남은 작업
- Airtable의 PD 19회차 레코드에 `캠프기수`·`과정코드` 입력 (사용자)
- 워커 중단으로 `RUNNING`에 남은 실행 정리 (기록 24)
