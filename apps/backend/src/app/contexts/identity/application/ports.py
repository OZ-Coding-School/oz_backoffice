"""identity 응용 계층이 쓰는 외부 연동 인터페이스."""

from typing import Protocol

from app.integrations.google.oauth import GoogleIdentity


class GoogleAuthenticator(Protocol):
    def authorization_url(self, *, state: str, code_challenge: str) -> str: ...

    async def exchange_code(self, *, code: str, code_verifier: str) -> GoogleIdentity: ...
