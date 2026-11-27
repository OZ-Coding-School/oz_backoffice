# 108. 계약 개편 (BE-4a)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A109 (A110은 BE-4b)
- 이전 기록: [107. 운영진 팀 목록 집계 (BE-3z2)](107_admin_team_stats.md)

## 배경
계약은 보통 기수 단위로 하고, 강사·멘토 외에 SW·장비 같은 과정 공통 계약도 있어 다른 화면처럼 과정·기수로 거르고 담당 범위를 적용해야 한다. 사용자가 계약 구조를 새로 정리했다(종류·상태·정산 유형·금액·당사자·취소/해지·변경 계약). 멘토링 정산 기준을 계약으로 옮기는 배정 개편(A110)은 BE-4b에서 한다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `educator/domain/enums.py` | `ContractType`(MENTOR·INSTRUCTOR·SW·EQUIPMENT·OTHER, 예전 `EducatorType` 대체), `ContractStatus` 7개, `SettlementType`, `PriceUnit`, `VatType`, `MentoringTimeBasis`, `TerminationReason` |
| `educator/domain/entities.py` | `EducatorContract` 개편: 과정 필수·기수 선택, 기간 선택, 금액 칸 검증(정산 유형별, 멘토는 시간·회 단가 + 노쇼 금액·정산 시간 기준), 당사자(멘토·강사 휴대폰 필수, 업체는 일반 번호·사업자등록번호·담당자), 상태 전이 `start_progress`·`sign`·`advance`·`end`·`cancel`·`terminate`, 서명 전 수정 `revised`·서명 후 변경 `amended`. `ContractAmendment` 엔티티 |
| `educator/domain/repositories.py`, `infrastructure/*` | 필터 `contract_types`·`bootcamp_id`·`cohort_id`·담당 범위 `ContractVisibility`, `list_due`(시작일이 된 SIGNED·종료일이 지난 ACTIVE), 변경 계약 저장소 |
| `migrations/models/35_*_contract_redesign.py` | 칸 추가·`educator_type` → `contract_type`, 기간·휴대폰 NULL 허용, `contract_amendments` 생성, CHECK 17개. **개발 DB의 기존 계약과 가입 전 멘토를 지운다**(A109⑪, 운영 배포 전) |
| `educator/application/contracts.py` | 담당 범위(조회 범위 밖 404·관리 범위 밖 403), 과정·기수 확인(`AcademyDirectory`), 진행·완료·종료·취소·해지·변경 계약·이력, 매일 작업 `advance_due` |
| `educator/application/ports.py` | `AcademyDirectory`(academy `AcademyCatalog`), `ContractPermissions`(access `PermissionChecker`) |
| `educator/presentation/admin_router.py` | 요청·응답 개편(과정 이름·기수 번호), `/progress`·`/sign`·`/end`·`/cancel`·`/terminate`(사유 본문), `/amendments`(등록·이력·변경 계약서 URL), 목록 `contract_type`(여러 개)·`bootcamp_id`·`cohort_id` 필터. `/confirm` 삭제 |
| `access/domain/catalog.py` | `educator.contract`를 기수에 속한 엔터티(`cohort_bound`)로 |
| `educator/application/mentor_onboarding.py` | 가입 연결 활성 판정을 SIGNED·ACTIVE로 (A109⑧) |
| `composition/contract_people.py` | 과정 이름·기수 번호, 변경 계약 등록자 이름 |
| `workers/tasks/contracts.py` | 매일 00:05 작업이 SIGNED → ACTIVE, ACTIVE → ENDED |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 재생성, 계약 화면 컴파일 맞춤(아래) |

### 정한 세부 (A109 안에서 기존 패턴을 따름)
- 컬럼·enum 이름: `contract_type`, `settlement_type`, `price_unit`(HOURLY·PER_SESSION·DAILY·MONTHLY·PER_ITEM), `vat_type`(기본 NOT_APPLICABLE), `mentoring_time_basis`(STUDENT_REQUEST·ACTUAL_DURATION), `business_registration_number`, `contact_person_name`, `cancel_reason`·`canceled_on`, `termination_reason`·`termination_detail`·`terminated_on`.
- 완료 처리 때 종료일이 이미 지났으면 바로 ENDED(예전 확정과 같음). 변경 계약으로 시작일이 지나면 바로 ACTIVE.
- `[종료]`는 종료일이 없는 ACTIVE만(`contract_has_end_date`). 해지 상세는 선택, 취소·해지 일자는 비우면 오늘.
- 변경 계약은 바뀐 항목만 전·후 값으로 남기고, 같은 값이면 `amendment_no_changes`. 당사자 이름은 변경 계약 항목이 아니다(연락처만). 변경 계약서는 다른 계약·변경 계약이 쓰지 않는 파일만.
- 오류 코드: `bootcamp_not_found`, `cohort_not_found`, `cohort_not_in_bootcamp`, `invalid_mentor_contract_terms`, `invalid_contract_amount`, `invalid_contract_party`, `invalid_business_registration_number`, `invalid_cancel_reason`, `contract_field_not_amendable`, `amendment_no_changes`, `contract_has_end_date`.

### 프론트 임시 수정 (다음 FE PR에서 화면 개편)
- `educator_type` → `contract_type`, 상태 라벨 3개 추가, 기간 없음 표시, 확정 = 진행 → 완료 두 번 호출, 해지는 합의 해지로 보낸다.
- **계약 추가는 과정·기수·금액 입력이 없어 서버가 받지 않는다**(과정 칸을 비워 보냄). 계약 화면 PR에서 입력을 더한다.

## 검증
- `ruff`, `mypy`(src·tests), `lint-imports`, `pytest`(973개)
- 개발 DB: `aerich upgrade` → `aerich migrate`(No changes) → `aerich downgrade -v 35` → `aerich upgrade`
- DBML 파서(`@dbml/core` 11.x) 통과
- 프론트: `lint`, `format:check`, `typecheck`, `vitest`(426), `build`, `e2e`(51)

## 남은 작업
- BE-4b(A110): 배정에 근거 계약, 정산이 계약을 읽음.
- 계약 화면 개편(과정·기수·금액·당사자·취소/해지·변경 계약), 배정 패널.
