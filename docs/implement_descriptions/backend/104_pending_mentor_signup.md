# 104. 가입 전 멘토의 가입 연결 (BE-3x)

- 상태: PR 진행 중
- 관련 PR: (작성 후 기록)
- 관련 결정: `docs/decisions.md` A105 (A104·F82, A31·A33·A82 변경)
- 이전 기록: [103. 가입 전 멘토와 멘토 계약 (BE-3w)](103_pending_mentors.md)

## 배경
계약을 먼저 만들면 가입 전 멘토가 생긴다(A104). 그 사람이 멘토로 가입하면 같은 멘토에 계정을 붙여야 배정·계약·프로필이 이어진다(A105).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `educator/application/mentor_onboarding.py` | 자동 연결: 연락처가 같은 가입 전 멘토가 하나면 계정 연결(닉네임·표시 이름, 진행 중 계약이 있으면 활성). 수동 승인 후보 `candidate_mentors`, 승인에 `mentor_id` |
| `educator/domain/repositories.py`, `infrastructure/repositories.py` | 가입 전 멘토 검색 `search_pending`(이름 또는 휴대폰, 검색어면 부분 일치) |
| `identity/application/signup_matching.py` | 멘토 매칭 결과: 연결 MATCHED, 둘 이상 AMBIGUOUS, 없으면 NO_MATCH |
| `identity/application/signup_review.py`, `presentation/approval_router.py` | 후보 응답 `mentors`, 승인 요청 `mentor_id` |
| 테스트 | 통합(자동 연결·활성 여부·둘 이상·없음, 수동 승인·이미 가입) |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성, 승인 테스트 데이터에 `mentors` |

## 주요 결정 (사용자 결정, A105)
- 가입하면 자동 연결·승인, 진행 중 계약이 있으면 활성.
- 수동 승인은 '미연결 계약' 대신 '가입 전 멘토'를 고른다(예전 계약 후보는 남김).

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 921 passed

## 남은 작업
- FE-18b 계약 화면, FE-15a 보완(가입 승인 멘토 탭에서 가입 전 멘토 고르기).
