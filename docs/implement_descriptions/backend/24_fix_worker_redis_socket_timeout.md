# 24. 워커 Redis 읽기 타임아웃으로 인한 반복 종료 수정

- 상태: PR 진행 중
- 관련 PR: (작성 예정)
- 이전 기록: [21. P5-2b 명단 동기화 동시 실행 락과 taskiq 작업](21_p5_2b_roster_sync_worker.md)

## 배경
P5-4 작업 중 실제 Airtable 데이터로 전체 명단 동기화를 워커에 보냈다. 실행 이력은 `RUNNING`에서 멈췄고, 워커 로그에는 프로세스가 약 5초마다 죽고 다시 뜨는 기록이 반복됐다(`redis.exceptions.TimeoutError: Timeout reading from redis:6379`, `worker-N is dead. Scheduling reload.`).

원인은 다음과 같다.
- redis-py 8.x는 연결의 기본 `socket_timeout`이 5초다(`ConnectionPool.from_url` 결과의 `orig_socket_timeout: 5`).
- taskiq-redis 1.2.4의 `ListQueueBroker.listen`은 `BRPOP`을 타임아웃 없이(무기한) 기다린다.
- 큐가 5초 동안 비어 있으면 소켓 읽기가 `TimeoutError`로 끝난다. 그런데 taskiq-redis는 `ConnectionError`만 잡는다. 그래서 수신 루프가 예외로 끝나고 워커 프로세스 전체가 종료된다.
- 프로세스가 죽으면 그 프로세스에서 실행 중이던 작업(명단 동기화)도 함께 중단된다. 실행 이력은 `RUNNING`, 동기화 락은 잡힌 채로 남는다.

## 구현 내용

| 경로 | 변경 |
| --- | --- |
| `apps/backend/src/app/workers/broker.py` | `ListQueueBroker(url=..., socket_timeout=None)`. 브로커 연결만 읽기 타임아웃을 끈다 |
| `apps/backend/tests/unit/test_worker_tasks.py` | 브로커 연결 풀의 `socket_timeout`이 `None`인지 확인하는 테스트 추가 |

## 주요 결정
- 브로커 연결에만 적용한다. 앱의 Redis 클라이언트(`REDIS_URL`, 토큰 저장·락)는 블로킹 명령을 쓰지 않으므로 기본 타임아웃을 그대로 둔다. 장애 때 오래 기다리지 않게 하기 위해서다.
- 의존성 버전을 바꾸는 방법(redis-py 7로 내리기)은 쓰지 않았다. 설정 한 줄로 해결되고, 이후 버전에서도 같은 기본값이 유지될 것이기 때문이다.

## 발견한 문제와 해결
- 중단된 실행 1건(`roster_sync_runs`, `SCHEDULED`/`ALL`)이 개발 DB에 `RUNNING`으로 남았다. 락 키 `oz:lock:roster-sync:all`도 남아 있었다. 실행은 `FAILED`로 바꾸고 락 키를 지웠다(개발 DB만).
- 워커가 작업 도중 죽어 `RUNNING`으로 남은 실행을 자동으로 정리하는 기능은 아직 없다. 락에는 TTL(30분)이 있어 결국 풀린다. 하지만 실행 이력은 수동으로 정리해야 한다. 남은 작업으로 둔다.

## 검증
- 수정 전: 워커를 재시작하면 약 5초마다 `worker-N is dead`가 반복됐다.
- 수정 후: 워커·스케줄러를 재시작하고 25초 동안 대기했다. 프로세스 종료 0회.
- `docker compose exec api`에서 ruff, ruff format, mypy, mypy tests, lint-imports(10 kept), pytest 326 passed

## 남은 작업
- 워커 중단으로 `RUNNING`에 남은 실행을 정리하는 기능 (예: 락 TTL보다 오래된 `RUNNING` 실행을 다음 주기 동기화 때 `FAILED`로 처리)
