"""Shared HTTP client configuration for third-party APIs."""

from __future__ import annotations

import time

import httpx
from django.conf import settings

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
MAX_BACKOFF_SECONDS = 8.0


class ExternalServiceError(Exception):
    """A third-party API (routing, weather, geocoding) failed or is
    unreachable.
    """

    def __init__(self, service: str, message: str):
        super().__init__(f"{service}: {message}")
        self.service = service
        self.message = message


def client(timeout: float | None = None) -> httpx.Client:
    return httpx.Client(
        timeout=timeout or settings.HTTP_TIMEOUT_SECONDS,
        headers={"User-Agent": settings.HTTP_USER_AGENT},
        follow_redirects=True,
    )


def _backoff(attempt: int, resp: httpx.Response | None) -> float:
    """Seconds to wait after `attempt` (1-based): Retry-After if given,
    else 1, 2, 4… capped at MAX_BACKOFF_SECONDS.
    """
    retry_after = resp.headers.get("Retry-After") if resp is not None else None
    if retry_after and retry_after.isdigit():
        return min(MAX_BACKOFF_SECONDS, float(retry_after))
    return min(MAX_BACKOFF_SECONDS, 2.0 ** (attempt - 1))


def _get_with_retries(
    service: str, url: str, params: dict | None, timeout: float | None
) -> httpx.Response:
    """GET `url`, retrying timeouts, 429 and 5xx with backoff.

    Returns the last response, which may still be an error status.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        is_last = attempt == MAX_ATTEMPTS
        try:
            with client(timeout) as c:
                resp = c.get(url, params=params)
        except httpx.TimeoutException as exc:
            if is_last:
                raise ExternalServiceError(service, "timed out") from exc
            time.sleep(_backoff(attempt, None))
            continue
        except httpx.HTTPError as exc:
            name = exc.__class__.__name__
            raise ExternalServiceError(
                service, f"request failed ({name})"
            ) from exc

        if is_last or resp.status_code not in RETRY_STATUSES:
            return resp
        time.sleep(_backoff(attempt, resp))
    raise AssertionError("unreachable: the last attempt always returns")


def _reason(resp: httpx.Response) -> str:
    """The provider's own explanation, e.g. Open-Meteo's
    {"reason": "Daily API request limit exceeded"}."""
    try:
        body = resp.json()
    except ValueError:
        return "no details"
    if isinstance(body, dict) and body.get("reason"):
        return str(body["reason"])
    return "no details"


def get_json(
    service: str,
    url: str,
    params: dict | None = None,
    timeout: float | None = None,
) -> dict | list:
    """GET a JSON document, raising ExternalServiceError on failure."""
    resp = _get_with_retries(service, url, params, timeout)
    if resp.status_code == 429:
        raise ExternalServiceError(
            service, f"rate limited ({_reason(resp)}), please retry later"
        )
    if resp.status_code >= 400:
        raise ExternalServiceError(
            service, f"HTTP {resp.status_code}: {resp.text[:200]}"
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise ExternalServiceError(service, "invalid JSON response") from exc
