# OZ 통합 백오피스

`prev_tools/`의 5개 기존 서비스(Auto_monitor, exam, mentor, ucansign, vacation)를 PostgreSQL 기반의 단일 백오피스로 통합하는 모노레포다. 백엔드 `apps/backend`(FastAPI), 프론트엔드 `apps/frontend`(React)로 나뉜다.

Git 브랜치·커밋·PR·구현 기록 규칙은 README를 따른다.

@README.md

## 현재 상태 (2026-11-10)

- **1단계: 멘토링 기능 이전.** DB 스키마(`docs/database_schema_v2.dbml`)는 멘토링 범위로 확정됐다.
- 백엔드: 프로젝트 뼈대·CI(#3), docker compose·floci S3(#4), compose 마운트 수정(#7) 완료. **P1 마스터 데이터 모델 완료**(identity·audit #6, academy #8, organization #9, 구현 기록 03·05·06). 수강생 명단은 `students`에 합쳤다(#10, decisions A10, 구현 기록 07). **P2 완료**: 인증 기반·운영진 Google 로그인(#11, 구현 기록 08), 운영진 최초 정보 입력(#12, 구현 기록 09). 운영진 가입 흐름은 decisions A11·A12. **P3-1 역할·권한 모델과 최고 관리자 CLI 완료**(#13, 구현 기록 10, decisions A14: `python -m app.cli create-super-admin <email>`). Google OAuth 콜백은 백엔드가 받는다(#14, decisions A15, 구현 기록 11). **P3-2 완료**: 권한 판정과 `require_permission`(#16, 구현 기록 13, decisions A16), 운영진 가입 승인·반려 API(#17, 구현 기록 14). 테스트 DB는 격리된 TortoiseContext와 전용 DB로 관리(#15, 구현 기록 12). **P3 완료**: 담당자 관리 API(#18, 구현 기록 15), 회원 역할 관리 API(#19, 구현 기록 16, decisions A17). **P4 완료**: 조직 관리 API(#20, 구현 기록 17), 학사 관리 API(#21, 구현 기록 18). Airtable 명단 동기화(#22~#25, 구현 기록 19~22, decisions A18·A19·B11), 과정-기수 테이블 마스터 동기화(#26, 구현 기록 23, decisions A20, D6 보완). 워커 Redis 읽기 타임아웃 수정(#27, 구현 기록 24). **P5 완료**: 수강생은 `취업운영시트 link`로 기수에 매핑(P5-4, #28, 구현 기록 25, decisions A21). 개발 DB에 실데이터(수강생 4,383명)가 동기화돼 있다. **P6-1 S3 어댑터 완료**(#29, 구현 기록 26, decisions B12, CI에 floci). P6은 4개 PR로 나눴다. **P6-2 educator 모델 완료**(#30, 구현 기록 27, decisions A22·A23). **P6-3 계약서 업로드·계약 API 완료**(#31, 구현 기록 28, decisions A24~A26, 매일 00:05 KST 계약 만료 작업). **P6 완료**: 계약 수동 연결·멘토 프로필 API(#32, 구현 기록 29, decisions A27·A28). 결정 사항은 반드시 사용자에게 묻는 규칙을 하네스에 추가(#33). **P7-1 발송 기반 완료**(#34, 구현 기록 30, decisions A29·B13: Gmail API 드라이버, SMS는 console). **P7-2 수강생·멘토 가입 완료**(#35, 구현 기록 31, decisions A30·B14: 이메일·SMS 인증, `member_signups`, 레이트 리밋). **P7-3 가입 자동 매칭 완료**(#36, 구현 기록 32, decisions A31: 신청 기수 명단·멘토 계약 매칭, 승인 알림 메일 워커). **P7-4 로그인·잠금·재설정 완료**(#37, 구현 기록 33, decisions A32). **P7 완료**: 운영진 승인 관리·재신청(#38, 구현 기록 34, decisions A33). **P8-1 기수 멘토링 설정·금지 시간대·추가 휴일 완료**(#39, 구현 기록 35, decisions A34·B15). **P8 완료**: 기수 멘토 배정·멘토 활성화·팀리드 권한(#40, 구현 기록 36, decisions A35·A36: 계약과 배정 분리, `mentor.manage`·`staff.assign`, TEAM_LEAD, 매일 00:00 KST 배정 만료). 외부 준비물 설정 가이드·운영 설정 참고사항 문서(#41, `docs/operations/`). **P9-1 멘토 불가 시간·신청 받기·기수 운영시간 완료**(#42, 구현 기록 37, decisions A37: 불가 시간만 등록(일회성·매일·매주), 기수 평일·주말 운영시간, 멘토 신청 받기 스위치, M1 변경). **P9 완료**: 신청 가능 시간 계산·조회(#43, 구현 기록 38, decisions A38: 운영시간 − 불가 시간 − 금지 시간대 − 세션 − 마감, `GET /mentors/{id}/available-times`). **P10-1 멘토링 팀 구성 완료**(#44, 구현 기록 39, decisions A39: 팀 멘토링 허용 기수·활성 배정 멘토·수강 중 팀원, `/me/mentoring-teams`). **P10-2a 시간 계좌·지급·조정·조회 완료**(#45, 구현 기록 40, decisions A40: 대상 4종 일괄 지급, 60분 단위·사유 필수, 만료 계좌는 차감만, Idempotency-Key). **P10 완료**: 명단 동기화 후 수강 종료 처리(#46, 구현 기록 41: 팀에서 빼기·1:1 잔여 회수, `mentoring.enrollment_ended.process`). 다음 작업은 **P11 신청·승인·반려·취소**.
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
| `docs/operations/external_setup.md` | 외부 준비물(Google 위임·Pub/Sub, SMS, OAuth, Airtable) 설정 방법과 상태 | |
| `docs/operations/production_notes.md` | 운영 배포 설정 참고사항(환경 변수, 실행 구성, S3, 첫 배포 순서, 정기 작업) | 운영 설정은 나중에 한 번에 한다. 운영 관련 사항이 생기면 여기에 추가 |

## 작업 방식 (사용자 선호)

- 문서와 응답은 한국어로 쓴다.
- 설계 결정이 필요하면 **질문으로 하나씩 확인**하고, 답을 받은 뒤 바로 반영한다. 확정된 결정은 `docs/decisions.md`에 추가한다.
- **`README.md`는 수정할 내용을 먼저 사용자에게 확인받고 고친다.** 확인받지 않은 문구(예시 등)는 바꾸지 않는다.
- 사용자가 작성한 원본 파일은 직접 덮어쓰지 말라고 하면 **복제본을 만들어** 수정한다. (예: `database_schema.dbml` → `database_schema_v2.dbml`)
- 사용자가 직접 수정한 파일은 그 상태를 기준으로 삼고, 바뀐 내용을 확인한 뒤 필요한 질문을 한다.
- 스키마를 바꾸면 DBML 파서로 검증한다. (`@dbml/core` 11.x. `checks`에는 `note` 속성을 쓸 수 없다)
