# 109. 배정의 근거 계약 (BE-4b)

- 상태: 완료
- 관련 PR: #187
- 관련 결정: `docs/decisions.md` A110 (A109⑨⑩, A111)
- 이전 기록: [108. 계약 개편 (BE-4a)](108_contract_redesign.md)

## 배경
계약을 기수 단위로 하게 되면서(A109) 멘토 단가가 계약과 기수 배정 두 곳에 생겼다. 사용자 결정(A110)으로 배정에는 필수 칸만 남기고 **근거 계약**을 가리키게 하며, 멘토링 정산은 근거 계약의 값으로 계산한다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `mentoring/domain/assignment.py` | `CohortMentor`에 `contract_id`, 정산 칸(정산 기준·단가 기준·단가·노쇼 금액) 삭제. `ensure_within_contract`(배정 기간이 계약 기간 안, 배정 종료일이 없으면 계약이 끝날 때까지), `trimmed_to`(계약 기간으로 줄이기, 남는 기간이 없으면 False), 수정 가능 항목은 기간·근거 계약. `AssignmentTerms` |
| `mentoring/domain/enums.py` | 비활성 사유 `CONTRACT_ENDED` |
| `mentoring/application/contract_basis.py` | 근거 계약 조건(그 멘토의 멘토 계약·SIGNED/ACTIVE·그 기수 또는 같은 과정 공통·기간), 후보 판정, 계약 → 정산 조건 변환(`terms_of`) |
| `mentoring/application/assignment_service.py` | 생성·수정·재활성화 때 근거 계약 확인, 근거 계약 후보 조회 |
| `mentoring/application/contract_sync.py` | 계약 종료·해지 → 활성 배정 비활성(`CONTRACT_ENDED`) + 그 기수 대기 신청 자동 취소, 계약 기간 변경 → 배정 기간 축소(남는 기간이 없으면 비활성) |
| `mentoring/application/mentor_activation.py` | 멘토 재활성화 때 근거 계약이 끝난 배정은 복구 후보·일괄 재활성화에서 뺀다 |
| `mentoring/application/settlement_service.py` | 정산 명세가 근거 계약의 단가·단가 기준·노쇼 금액·정산 시간 기준을 읽는다. 조건을 못 찾으면 `contract_terms_not_found`로 건너뜀 |
| `educator/application/ports.py`, `contracts.py` | `ContractLifecycleListener` 포트: 멘토 계약이 ENDED·TERMINATED가 되거나 기간이 바뀌면(전이·변경 계약·매일 작업) 같은 트랜잭션에서 알린다. 활성 배정의 근거인 계약은 다른 멘토로 옮기지 못한다(409 `contract_in_use_by_assignment`) |
| `educator/application/mentor_contracts.py` | 다른 컨텍스트용 멘토 계약 조회(`MentorContractQueries`) |
| `composition/assignment_contracts.py` | 포트를 멘토링 `AssignmentContractSync`로 채운다(API·매일 작업) |
| `mentoring/presentation/assignment_router.py` | 요청 `contract_id`, 응답에서 정산 칸을 빼고 `contract_id`·`contract`(근거 계약 요약: 제목·상태·과정/기수·기간·단가·단가 기준·노쇼 금액·정산 시간 기준). `GET /admin/cohorts/{cohort_id}/mentor-assignments/contract-candidates?mentor_id=`(배정 관리 권한) |
| `migrations/models/36_*` | `contract_id` 필수 FK·인덱스, 정산 칸·CHECK 삭제, 비활성 사유 CHECK에 `CONTRACT_ENDED`. **개발 DB의 기존 배정을 지운다**(A110) |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 재생성, 화면 컴파일 맞춤(아래) |

### 정한 세부 (A110·A111 안에서 기존 패턴을 따름)
- 오류 코드: `assignment_contract_mismatch`(그 멘토의 멘토 계약이 아님), `assignment_contract_not_effective`(SIGNED·ACTIVE 아님), `assignment_contract_other_cohort`, `assignment_outside_contract_period`, 근거 계약이 없으면 `contract_not_found`(404), 정산 건너뜀 `contract_terms_not_found`.
- 근거 계약 후보 API는 배정 관리 권한(`mentoring.assignment.manage`, 기수 범위)으로 기간을 빼고 고를 수 있는 계약만 돌려준다(기간은 저장할 때 확인).
- 계약 기간 변경은 시작일이 늦어져도 배정 시작일을 맞춘다(종료일과 같은 규칙). 재활성화도 근거 계약 조건을 다시 확인한다.
- 계약 변화로 자동 취소한 대기 신청은 채팅 안내 없이 감사 로그만 남긴다(계약 서비스에서 채팅 알림 도구를 조립하지 않음).
- 활성 배정의 근거인 멘토 계약은 다른 멘토로 옮길 수 없다(409).

### 프론트 임시 수정 (배정 패널 PR에서 개편)
- 배정 패널의 정산 입력 칸을 없애고 '정산 조건'은 근거 계약 값을 조회로만 보여 준다. 수정은 기간만 보낸다.
- **배정 추가는 근거 계약 고르기가 없어 서버가 받지 않는다**(`contract_id`를 비워 보냄). 배정 패널 PR에서 후보 API로 고르게 한다.
- 멘토 배정 카드·멘토 내 프로필의 정산 문구는 근거 계약 값으로, 비활성 사유 '계약 종료로 종료' 추가.

## 검증
- `ruff`, `mypy`(src·tests), `lint-imports`, `pytest`(979개)
- 개발 DB: `aerich upgrade` → `aerich migrate`(No changes) → `aerich downgrade -v 36` → `aerich upgrade`. 기존 배정 5건 삭제
- DBML 파서(`@dbml/core` 11.x) 통과
- 프론트: `lint`, `format:check`, `typecheck`, `vitest`(426, UTC·Asia/Seoul), `build`, `e2e`(51)

## 남은 작업
- 계약 화면 개편(과정·기수·금액·당사자·취소/해지·변경 계약), 배정 패널(근거 계약 고르기).

## 완료 반영 (2026-11-27)
- 백엔드 PR 규칙(CI 통과 후 병합, 사용자 위임)으로 병합. 다음은 계약 화면 개편과 배정 패널(근거 계약 고르기) 화면 PR.
