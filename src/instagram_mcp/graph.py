from __future__ import annotations

import json
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


def _accounts() -> dict[str, dict[str, Any]]:
    """The configured account registry as a map of alias -> account config.

    Uses IG_ACCOUNTS (a JSON object mapping alias -> {user_id, token, fb_page_id?,
    graph_version?, host?}) when set. Otherwise, for backward compatibility, if
    IG_USER_ID + IG_ACCESS_TOKEN are set it synthesizes a single account "default".
    """
    raw = os.environ.get("IG_ACCOUNTS")
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"IG_ACCOUNTS is not valid JSON: {e}") from e
        if not isinstance(data, dict) or not data:
            raise RuntimeError("IG_ACCOUNTS must be a non-empty JSON object of alias -> account")
        return data
    user_id = os.environ.get("IG_USER_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if user_id and token:
        return {"default": {"user_id": user_id, "token": token}}
    return {}


def _resolve(account: str | None) -> tuple[str, dict[str, Any]]:
    """Resolve an alias to (alias, config). None selects the sole account when
    exactly one is configured. Errors list valid aliases only — never tokens."""
    accounts = _accounts()
    if not accounts:
        raise RuntimeError(
            "No accounts configured: set IG_ACCOUNTS (JSON) or IG_USER_ID + IG_ACCESS_TOKEN"
        )
    if account is None:
        if len(accounts) == 1:
            alias = next(iter(accounts))
            return alias, accounts[alias]
        raise RuntimeError(
            f"Multiple accounts configured; specify `account`. Valid aliases: {sorted(accounts)}"
        )
    if account not in accounts:
        raise RuntimeError(f"Unknown account '{account}'. Valid aliases: {sorted(accounts)}")
    return account, accounts[account]


def _config(account: str | None = None) -> tuple[str, str]:
    alias, acct = _resolve(account)
    token = acct.get("token")
    if not token:
        raise RuntimeError(f"Account '{alias}' has no token (IG_ACCESS_TOKEN) configured")
    version = acct.get("graph_version") or os.environ.get("IG_GRAPH_VERSION", "v21.0")
    host = acct.get("host") or os.environ.get("IG_GRAPH_HOST", "graph.facebook.com")
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


def ig_user_id(account: str | None = None) -> str:
    alias, acct = _resolve(account)
    val = acct.get("user_id")
    if not val:
        raise RuntimeError(f"Account '{alias}' has no user_id (IG_USER_ID) configured")
    return val


def fb_page_id(account: str | None = None) -> str:
    alias, acct = _resolve(account)
    val = acct.get("fb_page_id")
    if not val:
        raise RuntimeError(
            f"Account '{alias}' has no fb_page_id configured; "
            "add fb_page_id to this account in IG_ACCOUNTS to use Facebook Page tools"
        )
    return val


def account_aliases() -> list[str]:
    """Sorted list of configured aliases."""
    return sorted(_accounts().keys())


def account_info(account: str) -> dict[str, Any]:
    """Non-secret metadata for an alias: user_id and fb_page_id only (never token)."""
    alias, acct = _resolve(account)
    return {"alias": alias, "user_id": acct.get("user_id"), "fb_page_id": acct.get("fb_page_id")}


async def get(path: str, *, account: str | None = None, **params: Any) -> Any:
    base, token = _config(account)
    q = _clean(params)
    q["access_token"] = token
    r = await _http().get(f"{base}/{path.lstrip('/')}", params=q)
    return _unwrap(r)


async def post(path: str, *, account: str | None = None, **fields: Any) -> Any:
    base, token = _config(account)
    r = await _http().post(
        f"{base}/{path.lstrip('/')}",
        params={"access_token": token},
        data=_clean(fields),
    )
    return _unwrap(r)


async def delete(path: str, *, account: str | None = None, **params: Any) -> Any:
    base, token = _config(account)
    q = _clean(params)
    q["access_token"] = token
    r = await _http().delete(f"{base}/{path.lstrip('/')}", params=q)
    return _unwrap(r)


async def paginate(
    path: str, *, account: str | None = None, max_pages: int = 5, **params: Any
) -> dict[str, Any]:
    """Follow paging.next up to max_pages and concatenate the `data` arrays."""
    results: list[Any] = []
    pages = 0
    next_url: str | None = None

    while pages < max_pages:
        if next_url is None:
            res = await get(path, account=account, **params)
        else:
            r = await _http().get(next_url)
            res = _unwrap(r)
        pages += 1
        results.extend(res.get("data", []))
        next_url = res.get("paging", {}).get("next")
        if not next_url:
            break

    return {"data": results, "pages_fetched": pages, "has_more": bool(next_url)}
