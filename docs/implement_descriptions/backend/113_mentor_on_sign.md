# 113. 새 사람의 멘토는 계약 완료 때 (BE-4f)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A115 (A104 변경)
- 이전 기록: [112. 멘토 계약은 다른 멘토로 옮기지 않음 (BE-4e)](112_mentor_contract_no_move.md)

## 배경
A104는 멘토 계약을 만들 때(초안) 이름·휴대폰이 같은 멘토에 붙이거나 가입 전 멘토를 만들었다. 사용자가 멘토 생성 시점을 초안에서 계약 완료로 옮기자고 했다. 기존 멘토의 추가 계약은 지금처럼 작성 단계에서 멘토를 고른다.

## 구현 내용
| 파일 | 내용 |
| --- | --- |
| `educator/application/contracts.py` | `create`: 멘토를 고른 경우만 연결. `sign`: 멘토 없는 멘토 계약이면 같은 사람 하나에 연결, 없으면 가입 전 멘토 생성, 둘 이상이면 409 `ambiguous_mentor` |
| `educator/presentation/admin_router.py` | 생성 요청 `mentor_id` 설명 |
| 마이그레이션 38 | CHECK `check_contract_mentor_from_sign`(멘토 계약은 SIGNED부터 멘토 필수) |
| `docs/database_schema_v2.dbml` | CHECK·칸 설명 |
| 테스트 | 초안에는 멘토가 없고 계약 완료 때 생기는 흐름, 같은 사람 연결, 둘 이상 409, 가입 전 멘토에 추가한 초안 삭제, 테스트 데이터에 멘토 |

## 주요 결정
- A115: 기존 멘토는 만들 때, 새 사람은 계약 완료 때 연결·생성.

## 검증
- 백엔드: ruff, mypy(src·tests), lint-imports, pytest 982개 통과. 마이그레이션 38 적용, `aerich migrate` 변경 없음. DBML 파서 통과.

## 남은 작업
- 계약 화면: 멘토 없는 초안의 멘토 줄 안내, 위저드의 새 사람 안내 문구(다음 화면 PR).
