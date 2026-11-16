# 55. P15-2 채팅 실시간 수신(SSE)·멘토링 이벤트 안내

- 상태: PR 진행 중
- 관련 PR: #60
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P15 (P15-2)
- 이전 기록: [54. P15-1 채팅방·메시지·읽음·운영진 열람](54_p15_1_chat.md)

## 배경
P15의 두 번째 PR이다(A57). P15-1의 REST 채팅에 실시간 수신(SSE)을 붙이고, 원본 mentor 서비스처럼 멘토링 신청·승인·취소 같은 이벤트를 그 채팅방에 안내 메시지로 남긴다. 멘토링 1단계 백엔드 계획(P1~P15)의 마지막 PR이다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `core/uow.py` | `after_commit(...)`: 열린 UoW를 contextvar로 찾아 커밋 후 작업 등록(없으면 바로 실행). `UnitOfWork.savepoint()`: 열린 트랜잭션 안의 savepoint |
| `mentoring/domain/chat.py` | `ChatEvent`(종류·방·메시지 ID), `ChatEventKind`(`message`·`message_deleted`·`read`) |
| `mentoring/infrastructure/chat_events.py` | `RedisChatEvents`: 사용자별 채널 `oz:mentoring:chat:user:<id>`에 발행·구독 |
| `mentoring/application/chat_service.py` | 커밋 뒤 알림(보내기·삭제는 참여자 모두, 읽음은 읽은 사람), `post_notice`(savepoint에 안내 저장 + 커밋 뒤 알림), `get_message` |
| `mentoring/application/chat_notices.py` | `MentoringNotices`: 이벤트별 안내 문구와 방(1:1은 신청자-멘토, 팀은 팀-멘토) |
| 신청·승인·자동 정리·기록 서비스 | `notices`(선택 인자)로 안내를 남긴다 |
| `mentoring/presentation/chat_router.py` | `GET /me/mentoring/chat/stream` (SSE), `StreamRenderer`, `chat_stream` |
| `mentoring/presentation/notices.py` | 채팅 서비스·안내 조립(여러 라우터 공용) |
| `main.py`, `workers/tasks/mentoring.py` | `app.state.chat_events`(Redis), 워커 작업은 작업마다 Redis 연결을 열고 닫는다 |

**SSE (`GET /api/v1/me/mentoring/chat/stream`)**
- `Authorization` 헤더로 연결한다(프론트는 fetch 기반 SSE 라이브러리).
- 첫 프레임은 `retry: 3000` + `event: ready`이다.
- 받는 이벤트:
  - `message`, `message_deleted`: 데이터는 MessageResponse.
  - `read`: 데이터는 내 ThreadResponse(안 읽음 수 갱신).
- 조용하면 15초마다 `: ping` 주석 줄을 보낸다.
- 알림에는 ID만 싣고, SSE를 받은 프로세스가 **받는 사람 기준으로 다시 읽어** 보낸다. 그래서 그 사이 자격이 없어진 방의 알림은 건너뛴다.

**안내 메시지 예**
- `[멘토링 신청] 주제: 이력서 · 60분 · 희망 일시: 11/20(금) 14:00, 11/21(토) 14:00`
- `[멘토링 승인] 11/20(금) 14:00~15:00 · 주제: 이력서`
- `[멘토링 반려] 주제: … · 사유: …`, `[멘토링 취소] (세션이면 일시) · 주제: … · 사유: …`, `[멘토링 변경] …`(새 신청 내용)
- `[멘토링 완료] 11/20(금) 14:00~15:00 · 진행 60분`, `[멘토링 노쇼] 11/20(금) 14:00~15:00`

안내를 남기는 곳: 신청, 변경, 승인, 반려, 신청자·멘토 취소, 운영진 취소, 대기 만료, 자동 정리(멘토·배정 비활성화, 신청 받기 끄기, 팀 멘토 변경, 팀에서 빠짐, 수강 종료, 불가 시간 충돌), 기록 제출.

## 주요 결정 (사용자 결정, A58)
- SSE도 **Authorization 헤더**로 확인한다(fetch 기반 SSE).
- **끊긴 사이의 알림은 다시 보내지 않고** 다시 조회로 맞춘다.
- 안내 메시지는 **일시·주제·사유**를 담는다.
- 안내는 원래 처리의 트랜잭션 안 **savepoint**에 남기고(실패해도 원래 처리 유지), 알림은 커밋 뒤에 보낸다.
- core `UnitOfWork`가 열린 트랜잭션을 contextvar로 알려 **UoW를 받지 않는 코드도 `after_commit`으로 커밋 후 작업을 등록**한다(새 패턴, 사용자 확인).

## 구현 세부
- **알림 실패:** Redis 발행이 실패해도 이미 커밋된 요청은 성공으로 두고 로그만 남긴다.
- **알림 대상:** 지금 그 방을 볼 수 있는 회원(멘토, 1:1 수강생 또는 현재 팀원)이다. 자격이 없어진 방에도 안내는 남기지만(운영진 열람) 알리지는 않는다.
- **같은 위치로 읽음:** 같은 위치로 다시 읽음 처리하면 알리지 않는다.
- **안내 본문:** 2,000자로 자른다. 안내도 상대의 안 읽음 수에 들어간다(A57).
- **savepoint:** Tortoise의 중첩 `in_transaction`(asyncpg savepoint)을 쓴다. 통합 테스트로 블록 실패 시 블록의 쓰기만 되돌려지는 것을 확인했다. 단위 테스트의 `FakeUnitOfWork.savepoint()`는 아무것도 하지 않는다.
- **선택 인자:** 신청·승인·자동 정리·기록 서비스의 `notices`는 선택 인자다(없으면 안내 없음). 기존 단위 테스트는 그대로 두고, 라우터·워커에서 항상 넘긴다.
- **ping 간격:** 구독 확인 메시지 직후 ping이 한 번 바로 나가고, 그 뒤 15초 간격이다(무해).
- **운영 참고사항:** `docs/operations/production_notes.md` 2-2에 nginx(`proxy_buffering off`, 타임아웃, gzip 제외)·로드 밸런서 유휴 타임아웃·Redis 연결 수를 추가했다.

## 검증
- 단위:
  - 커밋 뒤 알림 대상(팀원·멘토), 읽음은 본인만, 삭제, 알림 실패에도 성공
  - 안내 저장·커밋 뒤 알림·자격 없는 방은 알림 없음·저장 실패 시 None
  - 안내 문구(KST·요일·팀 방)
  - Redis 어댑터(fakeredis 발행·구독·다른 사용자 분리·깨진 알림 건너뜀)
  - SSE 생성기(ready·ping·건너뜀·끊기면 멈추고 구독 닫음)
- 통합: `after_commit`(열린 UoW 없으면 바로·커밋 후·롤백 시 버림), savepoint 부분 롤백
- API:
  - SSE 비로그인 401
  - 받는 사람 기준 렌더링(팀원에게 MessageResponse 프레임, 팀원이 아니면 건너뜀, 읽음 프레임). ASGI 테스트 클라이언트는 끝나지 않는 응답을 읽지 못해 렌더러를 직접 부른다.
  - 신청·승인·반려·취소·자동 취소(신청 받기 끄기)·기록 흐름에서 1:1 방에 안내 9개가 순서대로 남고 수강생 안 읽음 9
- 실제 uvicorn(컨테이너 안 별도 포트, 로그인만 가짜 회원, 개발 DB에 쓰지 않음):
  - `text/event-stream`, `X-Accel-Buffering: no`
  - `ready` 뒤 15초 간격 `: ping`
  - 볼 수 없는 방의 알림은 건너뜀
- 전체 827 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 코드 커밋을 worktree에서 각각 검사했다
- 스키마 변경 없음
- 개발 worker·scheduler를 재시작해 새 작업 코드로 정상 기동을 확인했다

## 남은 작업
- 프론트엔드 채팅 화면(fetch 기반 SSE, 재연결 시 다시 조회)
- 새 메시지 메일 알림은 알림 방식(M24) 결정 때
- 실제 Meet 세션으로 이벤트 → 수집 → 폴더 → API 전체 흐름 확인(P13 남은 작업)
