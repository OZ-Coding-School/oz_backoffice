# 70. 녹화 끝 시각 (BE-2e)

- 상태: 완료
- 관련 PR: #96
- 관련 결정: `docs/decisions.md` A71 (A69·F35)
- 이전 기록: [69. 세션 목록 상태 여러 개 필터 (BE-2d)](69_session_list_statuses.md)

## 배경
FE-5b 다시 보기에서 Meet 회의가 여러 번이면 녹화를 고른다(F35). 시안의 선택지는 '녹화 1 · 10:02 ~ 10:40'(시작~끝)인데, 녹화 목록 응답에는 녹화 시작(`started_at`)만 있었다. 사용자 결정으로 백엔드에서 녹화 끝을 내려준다(A71).

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `integrations/google/meet_events.py` | `MeetFile.ended_at`: Meet 녹화의 `end_time` |
| `mentoring/domain/artifact.py` | `ended_at`, `link_conference`가 비어 있는 녹화 끝도 채운다 |
| `mentoring/application/artifact_service.py` | 새 파일에 녹화 끝을 넣고, 이미 있는 파일은 보완 수집 때 채운다 |
| `mentoring/infrastructure/models/artifact.py`, `repositories.py` | `ended_at` 컬럼 저장·조회 |
| `migrations/models/28_…_artifact_ended_at.py` | `mentoring_artifacts.ended_at timestamptz NULL` (스키마만) |
| `mentoring/presentation/artifact_router.py` | 녹화 목록 응답 `ended_at` |
| `docs/database_schema_v2.dbml` | 같은 컬럼 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 다시 만들었다(F19) |

## 주요 결정 (사용자 결정, A71)
- 녹화 고르기에 시안대로 시작~끝을 보여 주려고 녹화 끝을 저장해 내려준다.
- 이미 수집된 영상은 매시 보완 수집이 채운다(세션 종료 7일까지). 그 뒤에도 없으면 화면은 시작 시각만 보여 준다.

## 발견한 문제와 해결
- 로컬에서 다른 프로젝트 컨테이너가 6379·8000 포트를 쓰고 있었다. 임시 compose 오버라이드로 redis 포트 노출을 빼고 api를 8001로 띄워 검사했다(저장소에는 넣지 않음).

## 검증
- 마이그레이션: upgrade → migrate "No changes detected" → `downgrade -v 28` → upgrade
- DBML 파서 검증 통과
- 테스트
  - 단위: Meet 녹화 끝 파싱, 보완 수집이 녹화 끝을 채움
  - 통합: 저장 왕복
  - API: 녹화 목록 응답에 `ended_at`
- **로컬 검사 (compose `api`):** ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 889 passed.
- **프론트엔드:** 다시 만든 타입으로 `typecheck` 통과
- **CI:** 통과. 사용자가 병합을 확인했다(2026-11-20)

## 남은 작업
- FE-5b 다시 보기
