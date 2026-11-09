"""요청의 클라이언트 IP (레이트 리밋용, decisions A30).

직접 연결 주소가 설정 `TRUSTED_PROXIES`(IP·CIDR)에 들 때만 `X-Forwarded-For`를 믿는다.
오른쪽(가장 가까운 프록시)부터 신뢰 프록시를 건너뛰고 처음 만나는 주소를 클라이언트로 본다.
신뢰 프록시가 없으면 헤더를 무시하므로, 헤더를 위조해 제한을 피할 수 없다.
"""

import ipaddress
from collections.abc import Sequence
from functools import lru_cache

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


@lru_cache(maxsize=16)
def parse_networks(values: tuple[str, ...]) -> tuple[Network, ...]:
    return tuple(ipaddress.ip_network(value.strip(), strict=False) for value in values if value)


def _trusted(address: str, networks: Sequence[Network]) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in network for network in networks)


def resolve_client_ip(
    peer: str | None, forwarded_for: str | None, trusted_proxies: Sequence[str]
) -> str:
    peer_ip = peer or "unknown"
    networks = parse_networks(tuple(trusted_proxies))
    if not networks or not forwarded_for or not _trusted(peer_ip, networks):
        return peer_ip
    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    for hop in reversed(hops):
        if not _trusted(hop, networks):
            return hop
    return hops[0] if hops else peer_ip
