"""taskiq 브로커와 스케줄러.

워커:      uv run taskiq worker app.workers.broker:broker app.workers.tasks.roster
스케줄러:  uv run taskiq scheduler app.workers.broker:scheduler app.workers.tasks.roster
(작업 모듈을 함께 넘겨야 등록된다. 새 작업 모듈을 만들면 docker-compose.yml 명령에도 추가한다)

태스크는 각 컨텍스트에서 `@broker.task`로 정의하지 않고, 이 패키지의 tasks 모듈에서
컨텍스트의 application 서비스를 호출하는 얇은 래퍼로 정의한다.
"""

from taskiq import TaskiqEvents, TaskiqScheduler, TaskiqState
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListQueueBroker
from tortoise import Tortoise

from app.core.config import get_settings
from app.core.database import build_tortoise_config

_settings = get_settings()

# redis-py 8은 연결 기본 socket_timeout이 5초다. 워커는 BRPOP으로 무기한 대기하는데,
# 큐가 5초 비면 TimeoutError가 나고 taskiq-redis는 ConnectionError만 잡아 워커 프로세스가
# 죽는다(실행 중이던 작업도 함께 중단). 브로커 연결만 읽기 타임아웃을 끈다.
broker = ListQueueBroker(url=_settings.taskiq_redis_url, socket_timeout=None)
scheduler = TaskiqScheduler(broker=broker, sources=[LabelScheduleSource(broker)])


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _startup(_: TaskiqState) -> None:
    await Tortoise.init(
        config=build_tortoise_config(_settings.database_url, with_aerich=False),
        _enable_global_fallback=True,
    )


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _shutdown(_: TaskiqState) -> None:
    await Tortoise.close_connections()
