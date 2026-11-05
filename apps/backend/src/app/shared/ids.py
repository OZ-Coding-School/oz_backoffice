"""ID 생성 (uuid7: 시간순 정렬 가능)."""

import uuid

import uuid_utils


def new_id() -> uuid.UUID:
    return uuid.UUID(int=uuid_utils.uuid7().int)
