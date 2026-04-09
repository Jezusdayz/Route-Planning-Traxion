import httpx

from api.config import settings

_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)


def get_client() -> httpx.AsyncClient:
    """Retorna un AsyncClient configurado con User-Agent y timeouts."""
    headers = {"User-Agent": settings.user_agent}
    return httpx.AsyncClient(headers=headers, timeout=_TIMEOUT)
