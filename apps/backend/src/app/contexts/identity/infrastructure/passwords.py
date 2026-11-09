"""비밀번호 해시 (argon2id, argon2-cffi, decisions B14).

해시 계산은 CPU를 쓰므로 스레드에서 실행해 이벤트 루프를 막지 않는다.
"""

import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


class Argon2PasswordHasher:
    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self._hasher = hasher or PasswordHasher()

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._hasher.hash, password)

    async def verify(self, hashed: str, password: str) -> bool:
        try:
            return await asyncio.to_thread(self._hasher.verify, hashed, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, hashed: str) -> bool:
        return self._hasher.check_needs_rehash(hashed)
