# 22. P5-2c 명단 동기화 관리 API

- 상태: 완료 (2026-11-09 병합)
- 관련 PR: #25
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P5 (P5-2c)
- 이전 기록: [21. P5-2b 명단 동기화 동시 실행 락과 taskiq 작업](21_p5_2b_roster_sync_worker.md)

## 배경
P5의 마지막 PR이다. 운영진(최고 관리자·매니저·조교)이 담당 범위 안에서 명단 동기화를 실행하고, 실행 상태·기수 명단·처리하지 못한 레코드를 확인하는 API를 만든다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `academy/presentation/roster_router.py` | `POST /admin/rosters/sync`(전체 범위), `POST /admin/bootcamps/{id}/rosters/sync`(과정 범위), `POST /admin/cohorts/{id}/rosters/sync`(기수 범위) → 202 + 실행. `GET /admin/rosters/sync-runs`(커서), `GET .../sync-runs/{id}`, `GET /admin/cohorts/{id}/rosters`, `GET /admin/rosters/unmapped` |
| `academy/application/roster_queries.py` | 최근 실행, 실행 상세, 최근 성공한 전체 동기화, 기수 명단 조회 |
| `academy/application/roster_sync.py` | `abort`(작업 전달 실패 시 실행 실패 처리 + 락 해제), `RosterSyncDispatcher` Protocol |
| `academy/.../repositories.py` | 실행 커서 조회(`list_recent`), 범위별 최근 성공 실행, 기수 명단(가입 여부·원천 삭제 필터) |
| `workers/tasks/roster.py`, `main.py` | `TaskiqRosterSyncDispatcher`를 `app.state.roster_sync_dispatcher`로 연결(B10). API도 작업을 보내므로 lifespan에서 브로커를 연결·해제 |
| `core/config.py` | `Settings.airtable_configured` (API·워커 공통) |
| `tests/` | 조회·abort(실제 DB), API: 요청 → 전달·락(409), 전달 실패 → 실패 기록·락 해제·재요청, 별칭 없음 422·Airtable 미설정 503, 조교 범위(자기 기수만 동기화·실행 이력도 자기 기수만, 다른 실행 404, 전체·실패 목록 403), 기수 명단 필터, 실패 목록 |

## 주요 결정
- 동기화 요청은 즉시 202와 실행(RUNNING)을 돌려준다(계획서). 상태는 실행 이력 API로 확인한다. 실제 동기화는 수 초지만 Airtable 응답이 느려질 수 있어 요청을 붙잡아 두지 않는다.
- **작업 전달 실패:** Redis 장애 등으로 전달하지 못하면 그 실행을 실패로 끝내고 락을 놓는다(503 `roster_sync_dispatch_failed`). 그렇지 않으면 TTL(30분) 동안 같은 범위를 다시 실행할 수 없다.
- **실행 이력 범위:** 실행마다 범위(전체 → 전체 권한, 과정 → 그 과정, 기수 → 그 기수)로 권한을 판정해 담당 범위 밖의 실행을 뺀다. 그래서 한 페이지가 `limit`보다 적을 수 있다. 다음 페이지는 `next_before` 커서로 이어 간다. 범위 밖 실행 상세는 존재를 드러내지 않도록 404로 응답한다.
- **실패 목록:** 가장 최근에 성공한 **전체** 동기화 기준이다. 과정·기수 동기화의 실패 목록은 그 범위만 담기 때문에, 전체 현황은 전체 동기화가 기준이 된다. 개별 실행의 실패 목록이 필요하면 실행 상세에 추가할 수 있다(지금은 건수만 노출).
- 기수 명단은 기본으로 원천에서 사라진 레코드를 뺀다. `include_removed=true`면 포함한다. 담당 조교도 볼 수 있다(`roster.sync`, 기수 범위).

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **314개 통과**
- 커밋 2개를 각각 워크트리로 꺼내 같은 검사 통과
- GitHub Actions (PR #25, run 42581460054): 첫 실행은 uv 내려받기 504(GitHub 일시 장애)로 실패했고, 다시 실행해 backend 잡 통과
- 사용자 확인: P5 진행 지시에 따라 CI 통과 후 병합
- api 컨테이너를 다시 띄워 lifespan의 브로커 연결과 함께 정상 기동하는 것을 확인했다(`/health` 200)

## 남은 작업
- 운영 배포 전에 운영과정마다 `airtable_cohort_prefix`를 설정하고 실제 기수를 등록한다. 그다음 전체 동기화를 실행해 실패 목록을 정리한다
- 가입 대기자 재매칭(동기화 후 PENDING 회원 자동 승인)은 P7 이후에 활성화한다(계획서)
