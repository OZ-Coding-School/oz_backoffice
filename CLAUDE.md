# OZ 통합 백오피스

`prev_tools/`의 5개 기존 서비스(Auto_monitor, exam, mentor, ucansign, vacation)를 PostgreSQL 기반의 단일 백오피스로 통합하는 모노레포다. 백엔드 `apps/backend`(FastAPI), 프론트엔드 `apps/frontend`(React)로 나뉜다.

Git 브랜치·커밋·PR·구현 기록 규칙은 README를 따른다.

@README.md

## 현재 상태 (2026-11-09)

- **1단계: 멘토링 기능 이전.** DB 스키마(`docs/database_schema_v2.dbml`)는 멘토링 범위로 확정됐다.
- 백엔드: 프로젝트 뼈대·CI(#3), docker compose·floci S3(#4), compose 마운트 수정(#7) 완료. **P1 마스터 데이터 모델 완료**(identity·audit #6, academy #8, organization #9, 구현 기록 03·05·06). 수강생 명단은 `students`에 합쳤다(#10, decisions A10, 구현 기록 07). **P2 완료**: 인증 기반·운영진 Google 로그인(#11, 구현 기록 08), 운영진 최초 정보 입력(#12, 구현 기록 09). 운영진 가입 흐름은 decisions A11·A12. **P3-1 역할·권한 모델과 최고 관리자 CLI 완료**(#13, 구현 기록 10, decisions A14: `python -m app.cli create-super-admin <email>`). Google OAuth 콜백은 백엔드가 받는다(#14, decisions A15, 구현 기록 11). **P3-2 완료**: 권한 판정과 `require_permission`(#16, 구현 기록 13, decisions A16), 운영진 가입 승인·반려 API(#17, 구현 기록 14). 테스트 DB는 격리된 TortoiseContext와 전용 DB로 관리(#15, 구현 기록 12). **P3 완료**: 담당자 관리 API(#18, 구현 기록 15), 회원 역할 관리 API(#19, 구현 기록 16, decisions A17). **P4 완료**: 조직 관리 API(#20, 구현 기록 17), 학사 관리 API(#21, 구현 기록 18). Airtable 명단 동기화(#22~#25, 구현 기록 19~22, decisions A18·A19·B11), 과정-기수 테이블 마스터 동기화(#26, 구현 기록 23, decisions A20, D6 보완). 워커 Redis 읽기 타임아웃 수정(#27, 구현 기록 24). **P5 완료**: 수강생은 `취업운영시트 link`로 기수에 매핑(P5-4, #28, 구현 기록 25, decisions A21). 개발 DB에 실데이터(수강생 4,383명)가 동기화돼 있다. **P6-1 S3 어댑터 완료**(#29, 구현 기록 26, decisions B12, CI에 floci). P6은 4개 PR로 나눴다. **P6-2 educator 모델 완료**(#30, 구현 기록 27, decisions A22·A23). 다음 작업은 **P6-3 계약서 업로드·계약 API**.
- 프론트엔드: 기술 스택만 정리됨 (`apps/frontend/CLAUDE.md`). 코드 없음.
- 원격 저장소: `OZ-Coding-School/oz_backoffice` (private). 모든 변경은 README 규칙대로 `develop`에서 작업 브랜치를 만들어 PR로 병합한다.

## 문서 지도

| 문서 | 내용 | 비고 |
| --- | --- | --- |
| `docs/decisions.md` | **확정된 결정 전체** (통합 범위, 멘토링 규칙, 데이터 규칙, 기술 선택, 미결정 항목) | 결정의 단일 출처. 다른 문서와 다르면 이 문서가 우선 |
| `docs/database_schema_v2.dbml` | 현재 DB 스키마 (멘토링 범위) | 작업 기준 스키마 |
| `docs/implement_plans/mentoring_phase1_backend.md` | **멘토링 1단계 백엔드 상세 구현계획** (PR P1~P15별 테이블·API·규칙·테스트, 권한표, 선행 준비물, 진행 체크리스트) | 다음 구현 작업의 기준 |
| `docs/implement_plans/backend_architecture.md` | 백엔드 구조 설계 (컨텍스트, 계층 규칙, 테스트 전략) | |
| `apps/backend/CLAUDE.md` | 백엔드 명령어·구조 규칙 | |
| `apps/frontend/CLAUDE.md` | 프론트엔드 기술 스택 | |
| `docs/analysis/<서비스>.md` | 기존 5개 서비스의 기능·동작·데이터 분석 | **로컬 전용** (`.gitignore`, `prev_tools/`와 함께). 기능을 이전할 때 원본 동작 확인용. 없으면 사용자에게 요청 |
| `docs/analysis/00_integration_requirements.md` | 통합·전환 요구사항 (초기 분석) | **로컬 전용**. 일부 미결정 항목은 `decisions.md`에서 확정됨 |
| `docs/database_schema_v2_mentoring_review.md` | 멘토링 스키마 리뷰와 결정 과정 | 결정 결과는 `decisions.md`에 정리 |
| `docs/database_schema.dbml`, `docs/database_schema_review.md` | 사용자가 작성한 최초 스키마 초안과 그 리뷰 | 이력 보존용. 작업 기준 아님 |
| `docs/implement_descriptions/` | 구현 기록 | 작업 완료 시 README 규칙대로 추가 |

## 작업 방식 (사용자 선호)

- 문서와 응답은 한국어로 쓴다.
- 설계 결정이 필요하면 **질문으로 하나씩 확인**하고, 답을 받은 뒤 바로 반영한다. 확정된 결정은 `docs/decisions.md`에 추가한다.
- **`README.md`는 수정할 내용을 먼저 사용자에게 확인받고 고친다.** 확인받지 않은 문구(예시 등)는 바꾸지 않는다.
- 사용자가 작성한 원본 파일은 직접 덮어쓰지 말라고 하면 **복제본을 만들어** 수정한다. (예: `database_schema.dbml` → `database_schema_v2.dbml`)
- 사용자가 직접 수정한 파일은 그 상태를 기준으로 삼고, 바뀐 내용을 확인한 뒤 필요한 질문을 한다.
- 스키마를 바꾸면 DBML 파서로 검증한다. (`@dbml/core` 11.x. `checks`에는 `note` 속성을 쓸 수 없다)
