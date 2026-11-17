# 58. 멘토링 크레딧 용어로 사용자 노출 문구 변경

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A60
- 이전 기록: [57. 운영진 멘티 목록·신청·세션 수 집계](57_mentee_list.md)

## 배경
Figma 수강생 화면을 다듬으면서 '시간 내역' 메뉴 이름을 정했다. 사용자 결정에 따라 멘토링 '시간 계좌'를 사용자에게는 **멘토링 크레딧**으로 부르기로 했다(A60). 프론트엔드 화면(Figma)은 함께 바꿨고, 백엔드에서도 사용자에게 보이는 문구를 맞춘다.

## 구현 내용
코드 동작은 그대로 두고 문구만 바꿨다.

| 위치 | 바꾼 문구 |
| --- | --- |
| `mentoring/domain/balance.py` | 크레딧 소유자, 사용 기간이 끝난 크레딧, 남은 크레딧 부족, 차감 예정 크레딧 오류 메시지 |
| `mentoring/application/balance_service.py`, `approval_service.py` | 크레딧을 찾을 수 없음, 크레딧 소유자 없음, 기본 지급 크레딧 설정 필요 |
| `mentoring/infrastructure/repositories.py` | 크레딧이나 신청이 있는 팀 삭제 불가, 이미 크레딧이 있음 |
| `access/domain/catalog.py` | 권한 설명 `mentoring.balance.grant`: "멘토링 크레딧 지급·조정" |
| `mentoring/presentation/*_router.py` | API 설명(OpenAPI)의 계좌·보류 표현을 크레딧·차감 예정으로 바꿈 |

## 주요 결정 (사용자 결정, A60)
- 사용자에게 보이는 곳만 '멘토링 크레딧'으로 부른다.
- 양은 시간 단위 그대로 둔다(남은 크레딧 2시간).
- 코드 이름, API 경로(`/balances`), 응답 필드, DB 이름은 바꾸지 않는다.
- 오류 코드(`insufficient_balance` 등)도 그대로 둔다.

## 구현 세부
- 권한 설명은 코드의 권한표가 기준이고 DB `role_permissions`는 사본이다. 개발 DB에는 `python -m app.cli seed-roles`로 반영했다. 운영은 배포 후 같은 명령으로 맞춘다.
- 로그 메시지(워커의 회수 로그 등)는 사용자에게 보이지 않아 바꾸지 않았다.

## 검증
- compose `api` 컨테이너에서 ruff, ruff format, mypy, mypy tests, lint-imports 통과
- pytest 830 passed (메시지 문자열을 직접 확인하는 테스트는 없음)

## 남은 작업
- 프론트엔드 구현 때 화면 문구도 '크레딧'으로 맞춘다(Figma 반영됨).
