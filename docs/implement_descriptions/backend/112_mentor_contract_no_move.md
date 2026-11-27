# 112. 멘토 계약은 다른 멘토로 옮기지 않음 (BE-4e)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A114 (A104 변경)
- 이전 기록: [111. 계약서 원본과 서명본 나눠 보관 (BE-4d)](111_signed_contract_file.md)

## 배경
계약 화면(#189)을 확인한 사용자가 "멘토는 이제 계약에 종속되므로 멘토 옮기기 기능은 사라져야 한다"고 했다. A104는 잘못 만든 계약을 바로잡으려고 멘토 계약을 상태와 관계없이 다른 멘토로 옮길 수 있게 했다.

## 구현 내용
| 파일 | 내용 |
| --- | --- |
| `educator/domain/entities.py` | `link()`: 멘토가 이미 정해진 멘토 계약을 다른 멘토로 바꾸면 `mentor_contract_move_forbidden` |
| `educator/application/contracts.py` | 옮기기 전 활성 배정 확인과 옮긴 뒤 빈 가입 전 멘토 지우기를 없앰 |
| `educator/application/ports.py`, `composition/assignment_contracts.py` | 쓰지 않는 `has_active_assignments` 포트 제거 |
| 테스트 | 옮기기 테스트를 금지 확인으로 바꿈(단위·API) |
| 프론트 | 생성 타입 갱신(스키마 변화 없음) |

## 주요 결정
- A114: 멘토 계약의 멘토는 바꿀 수 없다. 잘못 만든 계약은 초안이면 삭제, 진행 중이면 취소 후 새로.

## 검증
- 백엔드: ruff, mypy(src·tests), lint-imports, pytest 981개 통과.

## 남은 작업
- 계약 화면(#189)에서 [다른 멘토로 옮기기]를 없앤다.
