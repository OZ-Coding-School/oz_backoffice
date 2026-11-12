# 47. P12-1 Google Meet 공간 생성·막기

- 상태: PR 진행 중
- 관련 PR: #52
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P12 (P12-1)
- 이전 기록: [46. P11-3b 신청 연동](46_p11_3b_mentoring_integrations.md)

## 배경
P12는 PR 두 개로 나눴다(A48). 이번 PR은 승인된 세션에 Google Meet 공간을 만들고 링크를 응답에 담으며, 취소된 세션의 공간을 막는다. 회의 시작·종료·녹화 이벤트(Workspace Events·Pub/Sub)는 P12-2에서 한다.

Workspace 도메인 전체 위임에 Meet 범위가 아직 등록되지 않아 **실제 Google 호출은 확인하지 못했다**. 코드를 먼저 구현하고, 위임이 등록되면 `MEET_DRIVER=google`로 실제 호출을 테스트한다(A48).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `integrations/google/meet.py` | `GoogleMeetClient`: 공식 라이브러리(`google-apps-meet`) 비동기 클라이언트. 공간 생성(OPEN, 녹화·전사·스마트 메모 자동), 막기(RESTRICTED + 진행 중 회의 종료). 실패는 503 `meet_unavailable` |
| `core/meet.py`, `core/config.py` | `MEET_DRIVER`(disabled 기본 / google). 키·주최 계정이 없으면 클라이언트 없음 |
| `mentoring/domain/session.py` | `needs_space`, `needs_space_closed`, `attach_space`, `space_closed` |
| `mentoring/infrastructure/repositories.py` | 세션 `lock`, `list_needing_space`(시작 전·공간 없음), `list_needing_close`(취소·링크 남음) |
| `mentoring/application/meet_service.py` | `MeetSpaceService`: `ensure_space`·`close_space`·`sync` |
| `mentoring/application/approval_service.py` | 승인 커밋 후 공간 생성을 워커로 보낸다(`MeetSpaceScheduler`) |
| `workers/tasks/mentoring.py` | `mentoring.meet.create_space`(최대 3회, 5초·30초), `mentoring.meet.sync`(10분마다), `TaskiqMeetScheduler` |
| `mentoring/presentation/session_router.py` | 취소된 세션은 `google_meet_url`을 바로 숨긴다 |

## 주요 결정 (사용자 결정)
- A46: 공간 주최자는 `GMAIL_SENDER`, 링크가 있으면 바로 입장(OPEN), 녹화·전사·스마트 메모 자동.
- A47: Meet은 도메인 전체 위임(`meetings.space.created`·`meetings.space.readonly`), Drive는 폴더 공유로 서비스 계정 권한.
- A48: 코드 먼저, PR 2개, 공식 라이브러리, 취소 시 입장 제한, 승인 직후 재시도 + 10분 보완.

## 구현 세부
- **외부 호출과 트랜잭션:** 공간은 트랜잭션 밖에서 만들고, 붙일 때만 세션을 잠근다. 잠그는 사이 세션이 취소됐거나 다른 작업이 먼저 공간을 붙였으면, 방금 만든 공간은 막아 고아 공간이 열려 있지 않게 한다.
- **취소된 세션의 공간 막기:** 취소 경로(수강생·멘토·운영진 취소, 변경, 자동 정리)가 여럿이라 각 경로에서 작업을 보내지 않고 **10분마다 `sync`가 막는다**. 응답에서는 취소 즉시 링크를 숨기므로 링크가 새로 노출되지는 않지만, 이미 링크를 아는 사람은 최대 10분 동안 들어올 수 있다. 막은 뒤에는 `google_meet_url`을 지워 다시 대상이 되지 않게 한다(공간 이름은 기록으로 남김, 스키마 변경 없음).
- **설정이 없을 때:** `MEET_DRIVER=disabled`(기본)이거나 키·주최 계정이 없으면 작업이 아무것도 하지 않는다. 설정이 갖춰지면 `sync`가 시작 전 예정 세션의 공간을 채운다.
- **재시도:** 승인 직후 작업이 최대 3회 시도하고, 끝내 실패하면 `sync`가 다음 주기에 다시 만든다. `sync`의 건별 실패는 로그만 남긴다.
- **녹화·전사:** 공간 설정으로 자동 생성을 켠다. 라이선스가 지원하지 않는 항목은 Google이 무시한다(실제 동작은 위임 등록 후 확인).

## 검증
- 단위: 어댑터(생성 요청 설정 OPEN·녹화·전사·스마트 메모 ON, 막기 요청의 update mask·RESTRICTED, 없는 공간·진행 중 회의 없음 무시, 오류 → `meet_unavailable`, disabled·설정 누락 시 클라이언트 없음), 서비스(한 번만 붙임, sync로 생성·막기·멱등, 실패 다음 주기 재시도, 생성 중 취소되면 새 공간 막기, disabled), 승인 후 공간 생성 요청, 작업(이름·스케줄, 재시도 후 포기)
- 통합(PostgreSQL): 공간 필요·막기 대상 조회, 잠금·저장
- API: 승인 직후 링크 없음 → sync 후 링크 → 운영진 취소 즉시 링크 숨김 → sync가 공간 막기
- 전체 748 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 코드 커밋 4개를 worktree에서 하나씩 검사했다. 모두 통과했다(736 → 739 → 745 → 748 passed)
- **실제 Google 호출은 확인하지 못했다**(위임 미등록). 공간 설정 proto는 실제 라이브러리 타입으로 만들어 필드 값을 확인했다
- 스키마 변경 없음

## 남은 작업
- 위임 등록 후: `MEET_DRIVER=google`로 공간 생성·막기 실제 확인, 녹화·전사·스마트 메모 자동 생성 확인
- P12-2: Workspace Events 구독·갱신, Pub/Sub pull, 회의 시작·종료·녹화 이벤트 처리
- P13: 녹화 저장 방식(Drive 그대로 / 공유 드라이브 / S3) 결정
