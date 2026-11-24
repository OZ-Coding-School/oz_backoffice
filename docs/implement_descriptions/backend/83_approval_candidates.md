# 83. 가입 수동 승인 후보 (BE-3b)

- 상태: PR 진행 중
- 관련 PR: (작성 중)
- 관련 결정: `docs/decisions.md` A82, F60 (A31·A33)
- 이전 기록: [82. 운영진 유효 권한·담당 기수 (BE-3)](82_staff_access.md)

## 배경
FE-15a 회원 가입 승인 화면은 자동 매칭(A31)에 실패한 신청을 운영진이 직접 명단·계약에 연결한다(A33). 시안은 후보를 이름으로 여러 기수에 걸쳐 찾고, 이름·휴대폰이 맞는지 표시한다. 지금 명단 API는 기수 하나씩만 주고, 계약 목록은 미연결만 고르는 필터가 없다. 사용자는 백엔드 보완을 먼저 하기로 했다(A82).

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `academy/domain/repositories.py`, `infrastructure/repositories.py` | `search_claimable`: 미가입·원천 존재 명단을 기수 목록(없으면 전체)에서 이름·휴대폰(또는 q)으로 찾는다 |
| `academy/application/student_claims.py` | `ClaimCandidate`, `candidates` |
| `educator/domain/repositories.py`, `infrastructure/repositories.py`, `tests/fakes/educator.py` | `search_unlinked_mentor_contracts` |
| `educator/application/mentor_onboarding.py` | `ContractCandidate`, `candidate_contracts` |
| `identity/application/signup_review.py` | `SignupReviewService.candidates`: 수강생은 승인자 범위(과정 범위는 기수로 펼침)에서, 멘토는 `contract.manage`로. 이름·휴대폰 일치 표시와 정렬 |
| `identity/presentation/approval_router.py` | `GET /admin/approvals/{user_id}/candidates?q=`, 목록 응답에 신청 기수 과정명·번호 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 생성 타입 갱신 |

- 휴대폰 비교는 숫자만 본다. q 검색에서 휴대폰은 숫자 3자 이상일 때만 쓴다.
- 기수 이름은 한 번에 묶어 읽는다(`cohort_labels`).

## 주요 결정 (사용자 결정, A82·F60)
- 백엔드 보완 먼저, 후보 API 하나, 일치 많은 순 최대 20개, 신청 기수 이름 추가.
- FE-14b는 미루고 FE-15를 화면마다 PR 4개로.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 909 passed (통합 포함). API: 수강생 후보(일치 순·신청 기수·담당 밖 제외·q 검색·조교 범위), 멘토 후보(미연결 MENTOR만·휴대폰 일치·q 검색·조교 403), 목록의 신청 기수 이름
- 프론트엔드: `typecheck` 통과

## 남은 작업
- FE-15a 회원 가입 승인 화면
