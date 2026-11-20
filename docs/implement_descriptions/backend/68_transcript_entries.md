# 68. Meet 전사 문장 저장·조회 (BE-2c)

- 상태: PR 진행 중
- 관련 PR: #93
- 관련 결정: `docs/decisions.md` A68·A69 (A53·A54)
- 이전 기록: [67. 녹화 서명 링크와 스마트 메모 마크다운 (BE-2b)](67_artifact_link_markdown.md)

## 배경
FE-5 세션 상세의 영상 옆 패널은 전사본을 문장·시각·화자로 보여 준다. 문장을 누르면 영상이 그 시점으로 이동하고, 재생 중인 문장을 강조한다. 지금까지는 전사본을 PDF로만 중계했다. A68에서 Meet 전사 항목을 수집 때 받아 저장하기로 했다.

구현 전에 확인해 보니 Meet 참가자 정보에는 이메일이 없다(Google 계정 ID·표시 이름만). 그래서 A68의 '이메일로 화자 이름 바꾸기'를 할 수 없었고, 사용자와 다시 정했다(A69).
- 화자: 표시 이름이 같으면 서비스 이름으로 바꾸고, 같은 이름이 없으면 Meet 이름을 그대로 쓴다.
- 스키마: 새 테이블 하나와 `mentoring_artifacts` 컬럼 둘.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `mentoring/domain/transcript.py` | `TranscriptEntry`, 화자 이름 대조(`name_key`: 공백 제거·대소문자 무시, `speaker_name`: 같은 이름이면 서비스 이름, 비면 '참가자', 100자) |
| `mentoring/domain/artifact.py` | `conference_record`, `started_at`, `link_conference`(비어 있을 때만 채움) |
| `mentoring/domain/repositories.py`, `infrastructure/repositories.py`, `infrastructure/models/artifact.py` | `mentoring_transcript_entries` 모델·리포지토리(`add_many`, `artifacts_with_entries`, `list_by_artifact`). 파일 필드에 회의 기록·녹화 시작 추가 |
| `migrations/models/27_…_transcript_entries.py` | 아래 "마이그레이션" |
| `integrations/google/meet_events.py` | `MeetFile`에 회의 기록 이름·리소스 이름·녹화 시작. `transcript_lines`: 회의 기록 참가자 표시 이름을 한 번에 받고 전사 항목을 문장으로(빈 문장·시각 없는 항목 제외) |
| `mentoring/application/artifact_service.py` | 수집할 때 회의 정보를 채우고(먼저 만든 파일도 보완), 문장이 없는 전사본의 전사 항목을 받아 저장한다. 화자 별칭: 멘토 실명·닉네임 → 표시 이름(A28), 참여 수강생(1:1 신청자·지금 팀원) 이름 → 이름. `entries_for_user` |
| `mentoring/presentation/artifact_router.py` | `GET …/artifacts/{id}/entries`. 파일 목록 응답에 `conference_record`·`started_at` |
| `workers/tasks/mentoring.py` | 수집 서비스에 전사 문장 리포지토리·팀 리포지토리 연결 |
| `docs/database_schema_v2.dbml` | 테이블·컬럼 추가 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 다시 만들었다(F19) |

### 마이그레이션 (27)
- 테이블 `mentoring_transcript_entries`를 만든다.
  - 전사본 파일 FK(파일이 지워지면 함께 지운다, CASCADE)
  - 컬럼: `sequence`, `speaker_name`, `meet_name`, `text`, `started_at`, `ended_at`
  - `(artifact_id, sequence)` 유일, CHECK `sequence >= 0`
- `mentoring_artifacts`에 `conference_record`(varchar 255)와 `started_at`(timestamptz)을 추가한다. 둘 다 null 허용이다.
- **데이터를 넣지 않는다.** 기존 파일의 회의 정보와 전사 문장은 보완 수집(매시, 세션 종료 7일까지)이 채운다.

### 수집 규칙 (A69)
- 이벤트 즉시 수집과 매시 보완 수집 때 다음을 한다.
  - 같은 세션의 Meet 파일 목록을 다시 받아, 비어 있는 회의 기록·녹화 시작을 채운다.
  - 문장이 아직 없는 전사본만 전사 항목을 받는다.
- 전사 항목을 못 받으면(Meet 오류) 다음 수집에서 다시 한다.
- 영상 위치는 '문장 시작 − 같은 `conference_record` 영상의 `started_at`'으로 프론트가 계산한다.

### API

| API | 내용 |
| --- | --- |
| `GET /mentoring/sessions/{id}/artifacts/{artifact_id}/entries` | 참여자만. 전사본의 문장을 순서대로 `[{sequence, speaker_name, text, started_at, ended_at}]`. 아직 못 받았으면 빈 목록. 영상·스마트 메모와 남은 404. Meet 원래 이름(`meet_name`)은 내려주지 않는다 |
| `GET /mentoring/sessions/{id}/artifacts` (기존) | 각 파일에 `conference_record`, `started_at`(영상만) |

## 주요 결정 (사용자 결정, A69)
- 화자: Meet 표시 이름이 멘토 실명·닉네임이나 참여 수강생 이름과 같으면 서비스 이름으로 바꾸고, 아니면 Meet 이름을 쓴다. 멘토가 다른 이름으로 들어오면 실명이 보일 수 있다.
- 스키마는 새 테이블 하나와 파일 컬럼 둘로 한다.
- 못 받은 전사 항목은 보완 수집에서 다시 받는다.

## 발견한 문제와 해결
- Meet 참가자 정보에는 이메일이 없어 A68의 이메일 대조를 할 수 없었다. 사용자에게 다시 물어 A69로 정했다.

## 검증
- **DBML:** `@dbml/core` 11 `dbmlv2` 파서로 통과했다.
- **개발 DB:** `aerich upgrade` → `aerich migrate`("No changes detected") → `aerich downgrade -v 27` → `aerich upgrade`
- **테스트**
  - 단위
    - 화자 이름 대조(공백·대소문자, 모름, 빈 이름, 100자)
    - `link_conference`
    - Meet 어댑터: 녹화 시작·회의 기록·전사 리소스 이름, 참가자 이름을 붙인 문장, 빈 문장 제외, 오류
    - 서비스
      - 실패 후 다음 수집에서 저장
      - 한 번만 받기
      - 표시 이름(닉네임)으로 실명 감추기
      - 수강생 이름, 모르는 이름
      - 영상 404, 참여자 아님 404
      - 먼저 만든 파일의 회의 정보 보완
  - 통합: 회의 정보 저장 왕복, 문장 저장·순서·유일·CHECK
  - API: 문장 목록(서비스 이름, `meet_name` 없음), 영상·남 404, 목록의 새 필드
- **로컬 검사 (compose `api`):** ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 889 passed. 로컬 worker·scheduler를 다시 시작했다.
- **프론트엔드:** 다시 만든 타입으로 `typecheck` 통과
- 실제 Meet 전사 항목 수집은 아직 실제 세션으로 확인하지 않았다(테스트는 가짜 클라이언트). FE-5에서 실제 세션으로 확인한다.

## 남은 작업
- FE-5: 진행 기록·세션 상세(영상 서명 링크, 전사 문장 패널, 스마트 메모 마크다운)
