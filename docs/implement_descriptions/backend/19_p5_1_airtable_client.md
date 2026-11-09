# 19. P5-1 과정 별칭 컬럼과 Airtable 클라이언트

- 상태: 완료 (2026-11-09 병합)
- 관련 PR: #22
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P5 (P5-1)
- 이전 기록: [18. P4-2 학사 관리 API](18_p4_2_academy_admin_api.md), [07. 수강생 명단을 students에 합침](07_merge_student_rosters_into_students.md)

## 배경
P5(Airtable 명단 동기화)의 기반이다. 계획서는 Airtable에 "과정 코드" 필드와 "기수 번호" 필드가 따로 있다고 가정했다. 하지만 기존 디스코드 봇(`prev_tools/oz_discord_admin`)과 실제 데이터를 확인해 보니 구조가 달랐다. 실제 구조에 맞는 설정 컬럼과 Airtable 클라이언트를 먼저 만든다. 동기화 서비스는 P5-2에서 만든다.

## 실제 데이터 확인 (2026-11-09, 읽기 전용)
- 사용자가 `apps/backend/.env`에 `AIRTABLE_TOKEN`·`AIRTABLE_BASE_ID`·`AIRTABLE_TABLE_ID`를 넣었다.
- 메타데이터 API는 403이었다. 토큰에 `schema.bases:read`가 없기 때문이다. 그래서 레코드 4,551건을 읽어 필드 구조를 추정했다.
- 쓸 필드: `이름`, `전화번호`(`010-1234-5678`), `이메일`, `기수`(lookup 리스트 1개, `"<별칭> <N>기"`, 기수가 빈 레코드 106건), `상태`, `HRD상태`, `중도탈락일`, `훈련시작일`·`훈련종료일`.
- 과정 별칭은 13개다: BD, 디자이너, 게임개발, 백엔드, 프론트, AI리더, 헬스케어, BX, 1인창업, UD, MVP, CEO, 풀스택. 과정 코드와 다르다.
- `상태`가 `HRD상태`보다 세분화돼 있고 더 최신이다(예: 상태 하차 / HRD상태 중도탈락 242건, 상태 정상수료 / HRD상태 수강중 15건).
- 범위 수식 검증: `ARRAYJOIN({기수})='헬스케어 1기'` 59건, `FIND('헬스케어 ', ARRAYJOIN({기수}))=1` 366건, 두 과정의 OR 837건. 직접 집계한 값과 일치했다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `academy/domain/entities.py`, `infrastructure/models.py`, `migrations/models/6_...` | `bootcamps.airtable_cohort_prefix` (varchar 50, nullable, unique). 공백은 제거하고 빈 값은 null |
| `academy/application/academy_admin.py`, `presentation/admin_router.py` | 운영과정 생성·수정에서 별칭을 설정하고 비울 수 있다(null). 다른 과정과 겹치면 409 `airtable_prefix_taken` |
| `integrations/airtable/client.py` | `AirtableClient.list_records(table, formula, fields)`, `list_fields(table)`. pyairtable을 `asyncio.to_thread`로 호출하고, HTTP·연결 오류는 503 `AirtableError`로 바꾼다. 수식 이스케이프 헬퍼 `quote_formula_value`, `field_ref` |
| `core/config.py`, `.env.example` | `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_ID` |
| `pyproject.toml` | `pyairtable`, 개발 의존성 `types-requests` |

## 주요 결정
- **사용자 결정 (A18):** 과정 별칭은 `bootcamps`의 컬럼으로 두고 관리 API로 수정한다(환경변수 매핑 대신).
- **사용자 결정 (B11):** Airtable 연동은 pyairtable을 쓴다. 처음에 httpx로 직접 구현하던 클라이언트는 버렸다. 페이지네이션·429 재시도는 라이브러리에 맡기고, 우리 쪽 테스트는 인자 전달·응답 변환·오류 변환만 가짜 객체로 검증한다.
- **사용자 결정 (A19):** 수강 상태는 Airtable `상태`를 계속 따른다(A10 변경). 구현은 P5-2에서 한다.

## 발견한 문제와 해결
- 데이터 구조를 확인하는 출력에서 개인정보를 필드명으로만 걸렀다. 그래서 `휴가` 필드 값과 첨부파일 이름의 실명 일부가 작업 대화에 마스킹 없이 출력됐다(외부 전송 없음). 이후 조회는 범주형 값과 건수만 출력했다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **270개 통과**
- 개발 DB:
  - `aerich upgrade` 성공
  - `aerich migrate` → "No changes detected"
  - `aerich downgrade -v 5` → `upgrade` 성공
- 실제 Airtable 읽기 조회와 범위 수식 검증(위)
- 커밋 2개를 각각 워크트리로 꺼내 같은 검사 통과
- GitHub Actions (PR #22, run 42578694163): backend 잡 통과
- 사용자 확인: P5 진행 지시에 따라 CI 통과 후 병합

## 남은 작업
- P5-2: 동기화 서비스(범위·upsert·원천 삭제 판정·기수 매핑 실패·상태 매핑), taskiq 작업, API
- 운영자가 운영과정마다 `airtable_cohort_prefix`를 설정해야 동기화 대상이 된다
