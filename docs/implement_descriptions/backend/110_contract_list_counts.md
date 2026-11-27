# 110. 계약 목록 종류별 건수·과정 공통 함께 보기 (BE-4c)

- 상태: PR 진행 중
- 관련 PR: #188
- 관련 결정: `docs/decisions.md` A112 (A109·A111)
- 이전 기록: [109. 배정의 근거 계약 (BE-4b)](109_assignment_contract_basis.md)

## 배경
계약 화면 개편(F96)에서 행정 업무 모듈 상단에 과정·기수 선택기를 두고, 목록을 종류 탭(전체·멘토·강사·SW·장비·기타 + 건수)으로 나눈다. 기수를 고르면 그 기수 계약과 같은 과정의 과정 공통 계약을 함께 보여 줘야 한다. 지금 목록 API는 종류별 건수가 없고 기수 필터는 그 기수 계약만 돌려줘 백엔드를 먼저 보완한다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `educator/domain/repositories.py` | `ContractFilter.common_bootcamp_id`(기수 필터와 함께 과정 공통 포함), `count_by_types` |
| `educator/infrastructure/repositories.py` | 목록 조건을 `_filtered`로 모아 목록·건수가 같은 조건을 쓴다. 건수는 종류로 묶어 센다(종류 필터 제외) |
| `educator/application/contracts.py` | `list_contracts`가 `ContractList(views, total, counts)`를 돌려준다. `include_bootcamp_common`이면 기수의 과정을 `AcademyDirectory`로 찾아 채운다 |
| `educator/presentation/admin_router.py` | `GET /admin/contracts` 응답 `ContractListPage`(`counts`: 종류 5개), 쿼리 `include_bootcamp_common` |
| 프론트 `openapi.json`·`schema.gen.ts` | 다시 생성 |

## 주요 결정
- A112: 건수는 종류 필터만 무시하고 나머지 조건·담당 범위를 따른다. 전체 건수는 화면에서 합한다.
- 과정 공통 포함은 옵션(`include_bootcamp_common`, 기본 false)으로 둬서 기존 호출처(멘토 상세 계약 탭의 `mentor_id` 조회 등)의 동작을 바꾸지 않는다.

## 검증
- 백엔드: ruff, mypy(src·tests), lint-imports, pytest 980개 통과(단위: 건수·과정 공통, 통합: 저장소 필터·건수, API: 응답 `counts`·옵션).
- 프론트: `api:schema`·`api:gen` 후 typecheck, 계약·멘토 테스트 통과.

## 남은 작업
- 계약 화면 개편(F96) PR에서 상단 선택기·종류 탭·건수를 쓴다.
