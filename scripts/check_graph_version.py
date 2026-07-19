#!/usr/bin/env python3
"""Graph API version watchdog for the Instagram MCP fork.

Run weekly in CI. Does three things:
  1. Detects the newest Graph API version Meta has released (token-based probe).
  2. Smoke-tests BOTH the current default version and the newest version with
     read-only calls against your real IG account.
  3. Emits a machine-readable result to $GITHUB_OUTPUT so the workflow can
     open a bump PR / urgent issue.

Requires env: IG_ACCESS_TOKEN, IG_USER_ID
Exit code is always 0 unless the CURRENT default version is broken (exit 2),
so a red workflow == your live setup is at risk right now.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HOST = os.environ.get("IG_GRAPH_HOST", "graph.facebook.com")

def _load_accounts() -> dict[str, dict]:
    """IG_ACCOUNTS JSON map (alias -> {user_id, token, ...}); falls back to
    single-account IG_USER_ID + IG_ACCESS_TOKEN as alias 'default'."""
    raw = os.environ.get("IG_ACCOUNTS")
    if raw:
        return json.loads(raw)
    return {"default": {"user_id": os.environ["IG_USER_ID"],
                        "token": os.environ["IG_ACCESS_TOKEN"]}}

ACCOUNTS = _load_accounts()
_first = next(iter(ACCOUNTS.values()))
TOKEN = _first["token"]          # version probing is global; any account works
IG_USER_ID = _first["user_id"]
GRAPH_PY = Path(__file__).resolve().parent.parent / "src" / "instagram_mcp" / "graph.py"
MAX_PROBE_AHEAD = 8  # how many future major versions to probe past current


def call(version: str, path: str, token: str = None, **params) -> tuple[int, dict]:
    params["access_token"] = token or TOKEN
    url = f"https://{HOST}/{version}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "ig-mcp-version-watch"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": {"message": str(e)}}


def version_exists(version: str) -> bool:
    """A nonexistent version returns an 'Invalid version' / code 2500 error.
    Any other response (success, permission error, etc.) means it exists."""
    status, body = call(version, IG_USER_ID, fields="id")
    msg = (body.get("error") or {}).get("message", "")
    return not re.search(r"invalid version|unknown version", msg, re.I)


def smoke_test(version: str) -> list[str]:
    """Read-only checks per account. Returns failures tagged by alias."""
    failures = []
    for alias, acct in ACCOUNTS.items():
        uid, tok = acct["user_id"], acct["token"]
        status, body = call(version, uid, token=tok, fields="id,username")
        if status != 200 or body.get("id") != uid:
            failures.append(
                f"[{alias}] profile fetch failed (HTTP {status}): {json.dumps(body)[:200]}"
            )
        status, body = call(version, f"{uid}/media", token=tok, limit="1", fields="id,media_type")
        if status != 200 or "data" not in body:
            failures.append(
                f"[{alias}] media list failed (HTTP {status}): {json.dumps(body)[:200]}"
            )
    return failures


def main() -> int:
    src = GRAPH_PY.read_text()
    m = re.search(r'"IG_GRAPH_VERSION",\s*"v(\d+)\.0"', src)
    if not m:
        print("::error::Could not find default version in graph.py")
        return 2
    current_major = int(m.group(1))
    current = f"v{current_major}.0"

    # 1. Find newest available version
    latest_major = current_major
    for probe in range(current_major + 1, current_major + 1 + MAX_PROBE_AHEAD):
        if version_exists(f"v{probe}.0"):
            latest_major = probe
    latest = f"v{latest_major}.0"
    behind = latest_major - current_major

    # 2. Smoke-test current default (is production healthy TODAY?)
    current_failures = smoke_test(current)

    # 3. Smoke-test latest (is the bump safe?)
    latest_failures = smoke_test(latest) if behind > 0 else []

    out = {
        "current": current,
        "latest": latest,
        "behind": behind,
        "current_ok": not current_failures,
        "latest_ok": not latest_failures,
        "current_failures": "; ".join(current_failures),
        "latest_failures": "; ".join(latest_failures),
    }
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            for k, v in out.items():
                f.write(f"{k}={json.dumps(v) if isinstance(v, bool) else v}\n")
    print(json.dumps(out, indent=2))

    if current_failures:
        print(f"::error::CURRENT default {current} is FAILING live smoke tests")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
