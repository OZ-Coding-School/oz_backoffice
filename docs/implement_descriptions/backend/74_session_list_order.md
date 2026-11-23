# 74. 세션 목록 정렬 (BE-2i)

- 상태: 완료 (2026-11-23 병합)
- 관련 PR: #106
- 관련 결정: `docs/decisions.md` A75, F42
- 이전 기록: [73. 채팅 자격을 신청 이력 기준으로 (BE-2h)](73_chat_request_history.md)

## 배경
FE-8 수강생 홈은 다가오는 세션을 가까운 순으로 최대 3개 보여 준다(F42). 그런데 세션 목록은 시작 시각 최신순으로만 돌려줘서, `limit=3`으로 받으면 가장 먼 세션 3개가 온다. 사용자는 프론트에서 많이 받아 고르는 대신 백엔드에 정렬을 추가하기로 했다(A75).

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `mentoring/domain/session.py` | `SessionQuery.ascending` (기본 False) |
| `mentoring/infrastructure/repositories.py` | 세션 목록 정렬: ascending이면 `starts_at, id`, 아니면 `-starts_at, -id` |
| `mentoring/presentation/session_router.py` | 수강생·멘토 목록 쿼리에 `order=asc|desc` (기본 desc). 운영진 목록은 그대로 |
| `tests/fakes/mentoring.py` | 인메모리 세션 저장소도 같은 정렬 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 생성 타입 갱신 |

## 주요 결정 (사용자 결정, A75)
- 프론트에서 최대 100개를 받아 고르지 않고, 백엔드 정렬을 추가한다.
- 기본은 지금처럼 최신순이다. 기존 화면(진행 기록 등)은 바뀌지 않는다.
- 멘토 세션 목록도 같은 파라미터를 받는다(FE-13 멘토 홈에서 쓸 수 있다).

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports` 통과
- `pytest` 898 passed (통합 테스트 포함)
  - 통합: asc는 desc의 역순이고 이른 세션이 먼저 온다
  - API: `order=asc|desc` 200, 그 밖의 값 422

- GitHub Actions (PR #106): 백엔드·프론트엔드 검사·E2E 3개 통과
- 사용자가 병합을 확인했다(2026-11-23)

## 남은 작업
- FE-8 수강생 홈에서 사용
