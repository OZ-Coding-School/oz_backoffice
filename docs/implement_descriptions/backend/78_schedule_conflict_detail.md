# 78. 불가 시간 충돌 응답에 주제·신청자 (BE-2m)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` A79, F51 (A37·A45)
- 이전 기록: [77. 기록 제출 시 잔여 부족 처리 (BE-2l)](77_record_overtime_shortfall.md)

## 배경
FE-11 멘토 일정 시안의 충돌 확인 창은 겹치는 대기 신청·승인 세션의 주제와 신청자를 보여 준다('Django ORM 질문 · 가수강'). 불가 시간 등록·수정 응답의 충돌 목록에는 종류·id·시각만 있었다. 사용자는 백엔드에 주제·신청자를 더하기로 했다(A79).

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `mentoring/presentation/schedule_router.py` | `ConflictResponse.topic`·`requester_label`. `ConflictDetails`가 충돌 대상 신청·세션을 묶어 읽고 이름은 `NameBook`으로 채운다. 멘토 본인·운영진 대리 등록·수정 네 곳에 적용 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 생성 타입 갱신 |

- 주제는 대기 신청이면 신청 주제, 세션이면 세션 주제다.
- 신청자는 팀이면 팀 이름, 1:1이면 수강생 이름이다.
- 조회는 세션·신청·이름을 각각 한 번씩 묶어서 한다.

## 주요 결정 (사용자 결정, A79)
- 충돌 확인 창에 주제·신청자를 보여 주기 위해 백엔드 응답을 보완한다.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 902 passed (통합 테스트 포함). API: 미리보기 충돌의 주제·신청자
- 프론트엔드: `typecheck`, `vitest` 236 passed

## 남은 작업
- FE-11a 멘토 일정 보기, FE-11b 불가 시간 추가·수정·삭제·충돌 확인
