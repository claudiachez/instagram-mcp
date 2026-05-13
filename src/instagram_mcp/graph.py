from __future__ import annotations

import os
from typing import Any

import httpx


class GraphError(RuntimeError):
    """Raised when the Graph API returns a 4xx/5xx response."""

    def __init__(self, status: int, payload: Any):
        self.status = status
        self.payload = payload
        super().__init__(f"Graph API {status}: {payload}")

    def to_dict(self) -> dict[str, Any]:
        err = self.payload.get("error", {}) if isinstance(self.payload, dict) else {}
        return {
            "error": True,
            "status": self.status,
            "message": err.get("message") or str(self.payload),
            "code": err.get("code"),
            "subcode": err.get("error_subcode"),
            "fbtrace_id": err.get("fbtrace_id"),
        }


_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30.0)
    return _client


def _config() -> tuple[str, str]:
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("IG_ACCESS_TOKEN is not set")
    version = os.environ.get("IG_GRAPH_VERSION", "v21.0")
    host = os.environ.get("IG_GRAPH_HOST", "graph.facebook.com")
    return f"https://{host}/{version}", token


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _unwrap(r: httpx.Response) -> Any:
    try:
        body = r.json()
    except ValueError:
        body = r.text
    if r.status_code >= 400:
        raise GraphError(r.status_code, body)
    return body


def ig_user_id() -> str:
    val = os.environ.get("IG_USER_ID")
    if not val:
        raise RuntimeError("IG_USER_ID is not set")
    return val


async def get(path: str, **params: Any) -> Any:
    base, token = _config()
    q = _clean(params)
    q["access_token"] = token
    r = await _http().get(f"{base}/{path.lstrip('/')}", params=q)
    return _unwrap(r)


async def post(path: str, **fields: Any) -> Any:
    base, token = _config()
    r = await _http().post(
        f"{base}/{path.lstrip('/')}",
        params={"access_token": token},
        data=_clean(fields),
    )
    return _unwrap(r)


async def delete(path: str, **params: Any) -> Any:
    base, token = _config()
    q = _clean(params)
    q["access_token"] = token
    r = await _http().delete(f"{base}/{path.lstrip('/')}", params=q)
    return _unwrap(r)


async def paginate(path: str, max_pages: int = 5, **params: Any) -> dict[str, Any]:
    """Follow paging.next up to max_pages and concatenate the `data` arrays."""
    results: list[Any] = []
    pages = 0
    next_url: str | None = None

    while pages < max_pages:
        if next_url is None:
            res = await get(path, **params)
        else:
            r = await _http().get(next_url)
            res = _unwrap(r)
        pages += 1
        results.extend(res.get("data", []))
        next_url = res.get("paging", {}).get("next")
        if not next_url:
            break

    return {"data": results, "pages_fetched": pages, "has_more": bool(next_url)}
