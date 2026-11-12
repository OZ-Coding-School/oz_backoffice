# 48. P12-2 Meet 이벤트 구독·실시간 수신·처리

- 상태: PR 진행 중
- 관련 PR: #53
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P12 (P12-2)
- 이전 기록: [47. P12-1 Google Meet 공간 생성·막기](47_p12_1_meet_spaces.md)

## 배경
P12의 두 번째 PR이다. Meet 회의 시작·종료와 녹화 생성 이벤트를 받아 세션의 진행 상태·실제 시각·녹화 상태를 반영한다(M18). P12-1과 마찬가지로 Workspace 위임이 아직 등록되지 않아 **실제 Google 호출은 확인하지 못했고**, 설정이 없으면 구독·수신을 하지 않는다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `integrations/google/meet_events.py` | `GoogleMeetEvents`: 주최 계정 구독 생성·갱신, 회의 기록 조회. `MeetEventListener`: Pub/Sub streaming pull 수신기. `parse_message`(CloudEvents → 이벤트), `resolve_user_id`(주최 계정 ID) |
| `core/meet.py`, `core/config.py` | `MEET_PUBSUB_TOPIC`·`MEET_PUBSUB_SUBSCRIPTION`·`MEET_ORGANIZER_USER_ID`, 구독 클라이언트·수신기 조립 |
| `mentoring/domain/session.py` | `conference_started`·`conference_ended`(처음 시작·마지막 종료·첫 회의 기록, IN_PROGRESS까지만), `recording_generated` |
| `mentoring/infrastructure/` | 세션 `get_by_space`, `RedisProcessedEvents`(처리한 이벤트 ID 7일) |
| `mentoring/application/meet_event_service.py` | `MeetEventService.handle`: 중복 확인 → 회의 기록 조회 → 세션 반영 |
| `workers/tasks/mentoring.py` | worker 시작·종료 때 수신기 열기·닫기, `mentoring.meet.events.handle`(최대 3회), `mentoring.meet.events.subscribe`(6시간마다) |

## 주요 결정 (사용자 결정)
- A49: 구독은 공간마다가 아니라 **주최 계정 하나**. 한 공간에서 회의가 여러 번 열리면 **처음 시작 ~ 마지막 종료**. 중복은 **Redis 7일**.
- A50: 처음 구현한 1분 주기 pull 대신 **worker 프로세스에서 실시간 수신(streaming pull)** 하고, 받은 이벤트는 **작업으로 등록한 뒤 ack**한다. 별도 컨테이너·공개 주소 없음(M18 유지).

## 구현 세부
- **흐름:** Pub/Sub → (worker의 수신 스레드) 이벤트 파싱 → 작업 등록 → 등록 성공 시 ack / 실패 시 nack(다시 받음) → (워커 작업) 중복 확인 → 회의 기록 조회(이벤트 본문에는 회의 기록 이름만 있음) → 공간 이름으로 세션 → 잠그고 반영 → 처리 기록.
- **수신 스레드와 이벤트 루프:** 공식 라이브러리의 streaming pull은 자기 스레드에서 콜백을 부른다. 콜백은 작업 등록 코루틴을 worker의 이벤트 루프로 넘겨 끝날 때까지(최대 30초) 기다린 뒤 ack한다. 재연결·메시지 임대 연장은 라이브러리가 한다.
- **멱등:** 같은 이벤트를 다시 받아도 Redis 기록으로 거르고, Redis가 비어도 반영 자체가 최솟값·최댓값·처음 값만 남기는 방식이라 결과가 같다. 이벤트 순서가 뒤바뀌어도(종료가 먼저) 같다.
- **진행 상태:** 회의 이벤트는 예정(SCHEDULED)을 진행 중(IN_PROGRESS)으로만 바꾼다. 완료·노쇼는 멘토 기록(P13)으로만 정하며(M27), 기록 후 들어온 이벤트는 시각만 갱신한다.
- **무시하는 것:** 멘토링 세션이 아닌 공간(주최 계정의 다른 회의), 취소된 세션, 사라진 회의 기록, 모르는 형식의 메시지(바로 ack). 전사·스마트 메모 생성 이벤트는 받되 P13에서 처리한다(로그만).
- **구독 대상:** `//cloudidentity.googleapis.com/users/<주최 계정 ID>`. ID는 `MEET_ORGANIZER_USER_ID`가 없으면 위임 토큰의 tokeninfo `sub`로 찾는다(실제 동작은 위임 등록 후 확인, 안 되면 설정값으로 넣는다).
- **구독 갱신 주기(6시간):** A49는 "주기적으로 갱신"만 정했다. 구독 만료 전에 충분히 여러 번 갱신하도록 6시간으로 두었다(갱신은 ttl=0으로 최대 기간 연장). 사용자 확인 대상.
- **worker가 여러 개일 때:** 수신기도 여러 개가 되지만 Pub/Sub가 메시지를 나눠 준다.

## 발견한 문제와 해결
- **CI의 세션 끝 테스트 DB 삭제 실패:** CI에서 테스트는 모두 통과했지만 세션 종료 때 `DROP DATABASE ... WITH (FORCE)`를 실행하던 관리자 연결이 끊겨(`ConnectionDoesNotExistError`) 잡이 실패했다. PR #50에서도 같은 현상이 있었다(그때는 다시 실행해 통과). 관리자 연결은 `postgres` DB에 붙어 있어 FORCE가 끊는 대상이 아니고 로컬에서는 재현되지 않는다. 이 단계는 정리일 뿐이고 다음 세션이 시작할 때 DB를 지우고 새로 만들므로, 세션 끝 삭제가 연결 오류면 한 번 다시 시도하고 그래도 실패하면 경고만 남기게 했다(`tests/conftest.py`, 별도 `test:` 커밋). 테스트 실패를 숨기는 변경은 아니다.

## 검증
- 단위: 도메인(순서 뒤바뀜·여러 회의·중복, 완료 후 상태 유지, 취소 세션 무시, 녹화 상태), 서비스(반영·중복·무시 대상·Google 오류 시 예외로 재시도), 어댑터(메시지 파싱, 구독 생성 요청 필드·활성 구독 갱신 update mask, 회의 기록 조회·없음, 수신기 ack/nack·다른 스레드 콜백·종료, tokeninfo, Redis TTL, 설정 누락 시 비활성), 작업(이름·스케줄, 재시도, 설정 없으면 처리 안 함)
- 통합(PostgreSQL): 공간 이름으로 세션 조회
- worker 재시작 후 오류 없이 기동(설정 없음 → 수신 시작 안 함)
- 전체 758 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 코드 커밋 4개를 worktree에서 하나씩 검사했다(748 → 755 → 757 → 758 passed)
- **실제 Google 호출(구독·회의 기록·Pub/Sub)은 확인하지 못했다**(위임 미등록)
- 스키마 변경 없음

## 남은 작업
- 위임 등록 후: 구독 생성(주최 계정 ID 찾기 포함), 실시간 수신, 회의 시작·종료·녹화 이벤트 반영을 실제로 확인
- P13: 녹화·전사·스마트 메모 수집(저장 방식 결정 후), 멘토 기록·내부 메모
