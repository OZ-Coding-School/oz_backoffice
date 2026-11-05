"""taskiq 브로커와 스케줄러.

워커:      uv run taskiq worker app.workers.broker:broker
스케줄러:  uv run taskiq scheduler app.workers.broker:scheduler

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

broker = ListQueueBroker(url=_settings.taskiq_redis_url)
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
