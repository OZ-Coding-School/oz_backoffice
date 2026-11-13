# 51. P13-2 녹화·전사·요약 수집·폴더 정리·중계

- 상태: PR 진행 중
- 관련 PR: #56
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P13 (P13-2)
- 이전 기록: [50. P13-1 세션 기록·내부 메모·미제출 목록](50_p13_1_session_records.md)

## 배경
Meet이 만든 녹화·전사·스마트 메모를 세션별로 수집해 공유 드라이브 `멘토링 녹화`에 정리하고, Drive 권한 없이 백엔드가 중계한다(M19·M20·A53·A54). Workspace 위임에 `drive` 범위가 아직 등록되지 않아 **코드를 먼저 구현했고, 공유 드라이브 이동과 실제 중계는 등록 후 확인**한다(A54).

## 사전 확인 (2026-11-13, 실제 Drive)
- 서비스 계정은 주최 계정 `Google Meet` 폴더와 공유 드라이브 `멘토링 녹화`에 편집자 권한이 있다.
- 공유 드라이브 `멘토링 녹화` 아래에는 원래 mentor 서비스가 만든 `과정명/N기/멘토 실명/YYYY-MM` 구조가 이미 있다(예: `BX 디자이너/2기/…/2026-10`).
- 편집자 공유만으로는 개인 Drive 파일을 공유 드라이브로 옮길 수 없다(`canMoveItemOutOfDrive=false`). 소유자(주최 계정)를 대신하는 위임 `drive` 범위가 필요하다(A54). 이동 테스트에 쓴 임시 폴더는 서비스 계정에 영구 삭제 권한이 없어 휴지통으로 옮겼다.
- 주최 계정 `Google Meet` 폴더에는 멘토링이 아닌 회사 회의 파일도 있다. 코드는 Meet API가 알려 준 세션 파일만 다룬다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/artifact.py`, 마이그레이션 20 | `mentoring_artifacts`(세션·Drive 파일 유니크, 유형·상태 CHECK, 완료면 이름·형식 필수). PENDING → COMPLETED / FAILED |
| `integrations/google/meet_events.py` | `session_files`: 공간의 모든 회의 기록에서 생성이 끝난 녹화(VIDEO)·전사(TRANSCRIPT)·스마트 메모(SUMMARY) 파일 |
| `integrations/google/drive.py` | `GoogleDriveArchive`: 폴더 찾기·만들기(서비스 계정), 소유자로 이동(위임 drive), 정보 조회, 영상 Range 스트리밍·문서 PDF 내보내기 |
| `mentoring/application/artifact_service.py` | 수집·정리·7일 실패 처리, 열람 권한 확인·중계 |
| `mentoring/application/meet_event_service.py` | 녹화·전사·스마트 메모 생성 이벤트 → 수집 작업 요청 |
| `workers/tasks/mentoring.py` | `mentoring.meet.artifacts.collect`(최대 3회), `mentoring.meet.artifacts.sync`(매시 정각) |
| `mentoring/presentation/artifact_router.py` | 목록·중계 API |
| `core/meet.py`, `core/config.py` | `MEET_RECORDINGS_FOLDER_ID`, Drive 클라이언트 조립 |

**API**

| 대상 | 경로 |
| --- | --- |
| 담당 멘토·세션 수강생(1:1 신청자·팀원) | `GET /api/v1/mentoring/sessions/{id}/artifacts`, `GET .../artifacts/{artifact_id}/content` |
| 운영진(`mentoring.request.read`, 기수 범위) | `GET /api/v1/admin/cohorts/{cohort_id}/mentoring/sessions/{id}/artifacts[/{artifact_id}/content]` |

## 주요 결정 (사용자 결정)
- A53: 열람은 담당 멘토·운영진·참여 수강생. Drive 안에서 `멘토링 녹화/과정명/N기/멘토 실명/YYYY-MM`(세션 시작일 KST)로 정리하고 백엔드가 중계.
- A54: 최상위 폴더는 공유 드라이브(설정 `MEET_RECORDINGS_FOLDER_ID`). 이동은 위임 `drive`로 주최 계정을 대신해, 읽기·중계는 서비스 계정 자신의 권한으로. 전사·스마트 메모는 PDF로 내보내 중계.

## 구현 세부
- **수집:** 파일 생성 이벤트가 오면 그 세션을 바로 수집(작업)하고, 매시 정각 종료 7일 이내 세션을 보완 수집한다(M20). Meet API의 회의 기록 → 녹화·전사·스마트 메모 목록에서 `FILE_GENERATED`인 것만 가져온다. (세션, Drive 파일)이 유니크라 여러 번 수집해도 한 번만 남는다.
- **정리:** 폴더 경로를 한 단계씩 찾거나 만들고(이름 따옴표 이스케이프), 소유자 권한으로 옮긴 뒤 이름·형식·크기를 채워 COMPLETED. Drive 오류는 다음 주기에 다시 하고, 세션 종료 7일이 지나도 못 하면 FAILED. 과정·기수·멘토 이름을 못 찾으면 `미분류` 폴더로 보낸다.
- **중계:** 영상은 요청의 `Range`를 그대로 넘겨 206·`Content-Range`를 돌려주고, 문서는 PDF로 내보내 200으로 준다(Range 없음). 파일 전체를 메모리에 올리지 않고 스트리밍한다. `Content-Disposition: inline`(UTF-8 파일 이름), `Cache-Control: private, no-store`. 정리 전(PENDING)·실패 파일은 목록에 없고 중계도 404다.
- **권한:** 열람 권한은 세션 조회 규칙(`MentoringSessionQueries`)을 그대로 쓴다. 참여자가 아니면 404로 숨긴다.
- **비동기:** Drive 동기 클라이언트(google-api-python-client) 호출은 스레드에서, 중계는 httpx 비동기 스트리밍.

## 검증
- 단위: 도메인(정리·실패·문서 PDF), Meet 파일 조회(생성 끝난 것만·오류), Drive 어댑터(폴더 찾기·만들기·재사용·이스케이프, 소유자 이동·이미 그 폴더, 정보, 오류 → 503, 영상 Range 중계·헤더 걸러냄, PDF 내보내기, 404), 서비스(수집·폴더 경로·중복 없음, 실패 재시도·7일 후 FAILED, 열람 권한·중계 인자, 취소 세션·설정 없음), 이벤트 → 수집 요청, 작업(이름·스케줄·재시도)
- 통합(PostgreSQL): 파일 저장·중복 무시·CHECK 위반
- API: 목록(정리 전 숨김·문서 PDF 이름), 영상 206·Content-Range·inline, 문서 PDF, 정리 전 404, 비참여자 404, 운영진 목록·수강생 403 (Drive는 가짜로 바꿔 끼움)
- 마이그레이션 20: `upgrade` → `migrate`("No changes detected") → `downgrade -v 20` → `upgrade`, DBML 파서 검증
- 전체 786 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 코드 커밋 5개를 worktree에서 하나씩 검사했다(775 → 780 → 784 → 785 → 786 passed)
- **실제 Drive 이동·중계는 위임 `drive` 등록 후 확인한다**

## 남은 작업
- 위임 `drive` 등록 후: 테스트 회의 녹화로 수집 → 공유 드라이브 이동 → 목록·영상 Range·PDF 중계 실제 확인
- 멘토링 전용 주최 계정 분리(선택, 주최 계정의 다른 회의 파일과 분리)
- P14 정산
