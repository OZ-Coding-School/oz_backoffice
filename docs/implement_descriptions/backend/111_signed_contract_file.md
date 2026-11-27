# 111. 계약서 원본과 서명본 나눠 보관 (BE-4d)

- 상태: 완료
- 관련 PR: #190
- 관련 결정: `docs/decisions.md` A113 (A109⑥ 보완)
- 이전 기록: [110. 계약 목록 종류별 건수·과정 공통 함께 보기 (BE-4c)](110_contract_list_counts.md)

## 배경
계약 화면(#189)을 확인한 사용자가 상태를 바꿀 때 계약서를 함께 받자고 했다: 초안 → 진행 중은 미서명 계약서, 진행 중 → 계약 완료는 서명된 계약서. 그리고 계약서 원본과 서명된 계약서를 구분해 저장하기로 했다. 지금 계약은 계약서 파일을 하나만 가져, 서명본을 올리면 원본이 지워진 것으로 표시된다.

## 구현 내용
| 파일 | 내용 |
| --- | --- |
| `educator/domain/entities.py` | `signed_contract_file_id`, `SIGNED_FILE_STATUSES`(SIGNED·ACTIVE·ENDED·TERMINATED). `start_progress(contract_file_id=)`는 원본을 함께 받아 붙이고, `sign(signed_contract_file_id=)`는 서명본 필수·원본과 같은 파일이면 `signed_contract_file_same`. `ensure_file_for_status`가 서명본도 검사 |
| `educator/application/contracts.py` | `ContractView.signed_file`, 진행 때 새 원본이면 이전 원본을 지운 것으로 표시, 완료 때 서명본이 다른 계약·변경 계약에 쓰이지 않는지 확인, `file_url(signed=)` |
| `educator/infrastructure/models.py`·`repositories.py` | `signed_contract_file` OneToOne, `get_by_file`은 원본·서명본 둘 다 찾는다 |
| `educator/presentation/admin_router.py` | `POST …/progress` 본문 `{contract_file_id?}`(선택), `POST …/sign` 본문 `{signed_contract_file_id}`(필수), `GET …/file-url?signed=true`, 응답 `signed_contract_file` |
| 마이그레이션 37 | 칸 추가(UNIQUE·FK), 개발 DB의 서명 후 계약은 원본을 서명본으로도 채움, CHECK `check_contract_signed_file_required` |
| `docs/database_schema_v2.dbml` | 칸·CHECK 추가 |
| 프론트(임시) | 생성 타입 갱신. 개편 전 계약 화면의 [확정]은 진행까지만 한다(완료는 서명본이 필요해 #189 개편 화면에서). 테스트 목에 `signed_contract_file` |

## 주요 결정
- A113: 원본(미서명)과 서명본을 따로 둔다. 진행 때 원본, 완료 때 서명본을 함께 받는다. 서명본은 계약 완료부터 필수.

## 검증
- 백엔드: ruff, mypy(src·tests), lint-imports, pytest 981개 통과. 마이그레이션 적용 → 되돌리기 → 다시 적용, `aerich migrate` 변경 없음. DBML 파서 통과.
- 프론트: lint, format:check, typecheck, vitest 426개(UTC·Asia/Seoul), 계약 e2e 통과.

## 남은 작업
- 계약 화면(#189)의 상태 변경 창에서 원본·서명본 올리기.
