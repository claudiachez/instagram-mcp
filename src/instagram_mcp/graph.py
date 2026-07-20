from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any

import httpx

# Access tokens are passed as the `access_token` query param, and httpx logs the full
# request URL at INFO level — which would write tokens into the MCP server's log file.
# Keep those loggers at WARNING so credentials never hit disk.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


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


def _accounts_file_path() -> pathlib.Path:
    """Where account JSON is read from when IG_ACCOUNTS env is unset:
    IG_ACCOUNTS_FILE if set, else ~/.instagram-mcp/accounts.json."""
    override = os.environ.get("IG_ACCOUNTS_FILE")
    if override:
        return pathlib.Path(override)
    return pathlib.Path.home() / ".instagram-mcp" / "accounts.json"


def _accounts() -> dict[str, dict[str, Any]]:
    """The configured account registry as a map of alias -> account config.

    Resolution order:
      1. IG_ACCOUNTS env var (a JSON object mapping alias -> {user_id, token,
         fb_page_id?, graph_version?, host?}).
      2. A JSON file at IG_ACCOUNTS_FILE, or ~/.instagram-mcp/accounts.json by
         default (written by the guided setup).
      3. Backward compatibility: IG_USER_ID + IG_ACCESS_TOKEN -> single "default".
    """
    raw = os.environ.get("IG_ACCOUNTS")
    if raw is not None:
        raw = raw.strip()
        # A blank field, or an unsubstituted "${...}" placeholder passed by the .mcpb
        # extension config, must behave as "unset" so we fall back to the accounts file
        # instead of trying (and failing) to parse it as JSON.
        if not raw or raw.startswith("$"):
            raw = None
    if not raw:
        cfg = _accounts_file_path()
        if cfg.is_file():
            raw = cfg.read_text()
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
            "No accounts configured. Provide IG_ACCOUNTS (JSON) in the server's environment, "
            f"or save accounts to {_accounts_file_path()}. If this server is running remotely "
            "(a cloud sandbox), it cannot see files on your computer — install and run it "
            "locally, or inject IG_ACCOUNTS into its environment. Call health_check for details."
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


def diagnostics() -> dict[str, Any]:
    """Non-secret runtime diagnostics for troubleshooting scope/sandbox/path issues.
    Reports where the server is running and whether it can find accounts — never tokens."""
    path = _accounts_file_path()
    info: dict[str, Any] = {
        "home": str(pathlib.Path.home()),
        "accounts_file_path": str(path),
        "accounts_file_exists": path.is_file(),
        "ig_accounts_env_set": bool(os.environ.get("IG_ACCOUNTS")),
        "ig_accounts_file_env": os.environ.get("IG_ACCOUNTS_FILE"),
        # NB: use `or` (not the 2-arg default) so the release workflow's version grep
        # `"IG_GRAPH_VERSION", "vN.0"` matches ONLY the canonical default in _config().
        "graph_host": os.environ.get("IG_GRAPH_HOST") or "graph.facebook.com",
        "graph_version": os.environ.get("IG_GRAPH_VERSION") or "v21.0",
    }
    try:
        accts = _accounts()
        info["account_count"] = len(accts)
        info["aliases"] = sorted(accts.keys())
        if os.environ.get("IG_ACCOUNTS"):
            info["account_source"] = "env:IG_ACCOUNTS"
        elif path.is_file():
            info["account_source"] = f"file:{path}"
        elif os.environ.get("IG_USER_ID") and os.environ.get("IG_ACCESS_TOKEN"):
            info["account_source"] = "legacy:IG_USER_ID+IG_ACCESS_TOKEN"
        else:
            info["account_source"] = "none"
    except Exception as e:  # diagnostics must never raise
        info["account_count"] = 0
        info["aliases"] = []
        info["account_source"] = f"error: {type(e).__name__}: {e}"
    return info


def _redact(obj: Any, token: str) -> Any:
    """Strip the access token out of any string in a response. The Graph API echoes
    the token back inside `paging` next/previous URLs, so without this it would reach
    tool output, the model, and any transcript. Keeps credentials out of responses."""
    if not token:
        return obj
    if isinstance(obj, str):
        return obj.replace(token, "REDACTED")
    if isinstance(obj, list):
        return [_redact(v, token) for v in obj]
    if isinstance(obj, dict):
        return {k: _redact(v, token) for k, v in obj.items()}
    return obj


async def get(path: str, *, account: str | None = None, **params: Any) -> Any:
    base, token = _config(account)
    q = _clean(params)
    q["access_token"] = token
    r = await _http().get(f"{base}/{path.lstrip('/')}", params=q)
    return _redact(_unwrap(r), token)


async def post(path: str, *, account: str | None = None, **fields: Any) -> Any:
    base, token = _config(account)
    r = await _http().post(
        f"{base}/{path.lstrip('/')}",
        params={"access_token": token},
        data=_clean(fields),
    )
    return _redact(_unwrap(r), token)


async def delete(path: str, *, account: str | None = None, **params: Any) -> Any:
    base, token = _config(account)
    q = _clean(params)
    q["access_token"] = token
    r = await _http().delete(f"{base}/{path.lstrip('/')}", params=q)
    return _redact(_unwrap(r), token)


async def paginate(
    path: str, *, account: str | None = None, max_pages: int = 5, **params: Any
) -> dict[str, Any]:
    """Follow paging.next up to max_pages and concatenate the `data` arrays."""
    # Fetch raw (not via get()) so we can follow the tokenized paging.next URL
    # internally; the returned payload omits paging URLs and is redacted anyway.
    base, token = _config(account)
    results: list[Any] = []
    pages = 0
    next_url: str | None = None

    while pages < max_pages:
        if next_url is None:
            q = _clean(params)
            q["access_token"] = token
            r = await _http().get(f"{base}/{path.lstrip('/')}", params=q)
        else:
            r = await _http().get(next_url)
        res = _unwrap(r)
        pages += 1
        results.extend(res.get("data", []))
        next_url = res.get("paging", {}).get("next")
        if not next_url:
            break

    return {"data": _redact(results, token), "pages_fetched": pages, "has_more": bool(next_url)}
