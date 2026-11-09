# 20. P5-2a Airtable 명단 레코드 해석과 동기화 서비스

- 상태: 완료 (2026-11-09 병합)
- 관련 PR: #23
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P5 (P5-2a)
- 이전 기록: [19. P5-1 과정 별칭 컬럼과 Airtable 클라이언트](19_p5_1_airtable_client.md)

## 배경
P5-1에서 확인한 실제 Airtable 구조(A18)와 사용자 결정(A19: 수강 상태는 Airtable `상태`를 따름)을 바탕으로 동기화 로직을 만든다. 범위 수식, upsert, 원천 삭제 판정, 기수 매핑 실패를 처리하는 서비스까지가 이번 범위다. 동시 실행 락, 주기 작업, API는 P5-2b에서 만든다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `academy/domain/roster.py` | 순수 함수. 기수 라벨 분해(`"헬스케어 3기"` → 별칭·번호), 이름·휴대폰·이메일 정규화(형식이 틀린 휴대폰·이메일은 비움), `상태` → 수강 상태(A19), `HRD상태` → HRD-Net 상태, 종료일(중도탈락일 / 훈련종료일), 범위 수식(`ARRAYJOIN`·`FIND`·OR) |
| `academy/domain/enums.py`, `migrations/models/7_...` | `StudentStatus.UNKNOWN`(HRD상태가 확인필요·미입력·모르는 값), CHECK 제약 갱신 |
| `academy/domain/entities.py` | `Student.sync_enrollment`: 수강 상태와 종료 정보를 맞춘다. 기수 이동(TRANSFERRED)은 덮어쓰지 않는다. 등록일보다 빠른 종료일은 비운다 |
| `academy/.../repositories.py` | 레코드 ID 일괄 조회, 범위 기수의 Airtable 출처 수강생 조회, `add_many`(bulk_create), `save_many`(bulk_update) |
| `academy/application/roster_sync.py` | `RosterSyncService.create_run / execute`. Airtable 조회는 트랜잭션 밖에서 하고, 반영은 한 트랜잭션에서 한다. 실패는 실행 이력에 기록한다 |
| `tests/fakes/roster.py` | 동기화가 만드는 범위 수식을 해석하는 가짜 원천 |
| `tests/` | 해석·매핑 단위 테스트, 동기화 통합 테스트 7개(실제 DB) |

## 주요 결정
- **실패 목록과 건너뛰기를 나눈다.** 운영진이 처리해야 하는 레코드만 실패 목록에 남긴다. 사유는 `cohort_not_found`(별칭은 맞는데 DB에 기수가 없음), `cohort_changed`(레코드의 기수가 바뀜), `invalid_name`이다. 기수가 비었거나 별칭이 설정되지 않은 과정의 레코드는 대상이 아니라서 건너뛴다. 실데이터 4,551건 중 대부분이 오래된 기수라, 모두 실패 목록에 넣으면 목록이 쓸모없어진다.
- **수강 상태 보조 판단:** `상태`가 없거나 모르는 값이면 `HRD상태`로 판단하고, 둘 다 없으면 수강 중으로 본다(새로 추가된 레코드가 대부분 이 경우다).
- **HRD상태 `UNKNOWN`:** `hrd_net_status`는 필수 컬럼이다. 확인필요·미입력을 다른 값으로 억지로 바꾸지 않으려고 새 값을 추가했다.
- **종료일:** 중도포기면 `중도탈락일`, 수료·조기취업이면 `훈련종료일`을 쓴다. 원천 날짜가 등록일(기수 시작일)보다 빠르면 데이터 오류로 보고 비운다.
- **기수가 바뀐 레코드**는 자동으로 옮기지 않는다(계획서 확정 사항). 기존 수강 등록은 그대로 두고 실패 목록에 기존 수강생 ID와 함께 남긴다.
- **가입한 수강생의 이름·휴대폰 변경**은 연결을 유지하고 감사 로그(`academy.student.source_identity_changed`)를 남긴다.
- **원천 삭제 판정 범위:** 실행 범위에 속한 기수 중 Airtable에서 온 수강생만 대상이다. 다시 나타나면 `apply_source`가 표시를 되돌린다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **296개 통과**
- 개발 DB:
  - `aerich upgrade` 성공
  - `aerich migrate` → "No changes detected"
  - `aerich downgrade -v 6` → `upgrade` 성공
- 커밋 2개를 각각 워크트리로 꺼내 같은 검사 통과
- GitHub Actions (PR #23, run 42579711712): backend 잡 통과
- 사용자 확인: P5 진행 지시에 따라 CI 통과 후 병합
- 동기화 시나리오(실제 DB + 가짜 원천)
  - 전체 동기화: 생성·실패 목록·범위 밖 건너뛰기를 확인했고, 다시 실행하면 변경 0(멱등)
  - Airtable 상태 반영과 기수 이동 유지
  - 기수 동기화가 다른 기수를 건드리지 않음, 다시 나타난 레코드 복구
  - 기수 변경 레코드를 실패 목록에 기록, 가입 수강생 신원 변경 감사 로그
  - 실패를 실행 이력에 기록, 별칭이 없는 과정 거부, 별칭이 하나도 없으면 아무것도 하지 않음

## 남은 작업
- P5-2b: Airtable 원천 어댑터, 동시 실행 락(Redis), taskiq 주기·수동 작업, 관리 API, 실제 Airtable로 끝까지 실행 확인
