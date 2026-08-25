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
    raw = (os.environ.get("IG_ACCOUNTS") or "").strip()
    if raw:
        try:
            accounts = json.loads(raw)
        except json.JSONDecodeError as e:
            sys.exit(f"IG_ACCOUNTS is set but is not valid JSON ({e}). Expected "
                     '{"default": {"user_id": "...", "token": "..."}}')
        if not accounts:
            sys.exit("IG_ACCOUNTS parsed to an empty map, so there is no account "
                     "to smoke-test. Set it to a JSON map of alias -> "
                     '{"user_id": ..., "token": ...}')
        return accounts
    user_id = os.environ.get("IG_USER_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not user_id or not token:
        sys.exit(
            "No Instagram credentials in the environment, so the watchdog cannot "
            "smoke-test anything.\n"
            "In CI this means the repo secret IG_ACCOUNTS is missing or empty: set it "
            "under Settings > Secrets and variables > Actions to a JSON map like\n"
            '  {"default": {"user_id": "<ig user id>", "token": "<long-lived token>"}}\n'
            "The workflow passes IG_ACCOUNTS only. IG_USER_ID + IG_ACCESS_TOKEN are "
            "the local-run fallback."
        )
    return {"default": {"user_id": user_id, "token": token}}

ACCOUNTS = _load_accounts()
_first = next(iter(ACCOUNTS.values()))
TOKEN = _first["token"]          # version probing is global; any account works
IG_USER_ID = _first["user_id"]
GRAPH_PY = Path(__file__).resolve().parent.parent / "src" / "instagram_mcp" / "graph.py"
MAX_PROBE_AHEAD = 8  # how many future major versions to probe past current


def call(version: str, path: str, token: str = None, **params) -> tuple[int, dict]:
    if token != "":                      # token="" sends no credentials at all
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
    """Meta publishes no version list, so probe /me with NO token: the answer
    then depends on the version alone, never on permissions.

      live version      -> "An active access token must be used ..."
      unreleased version-> "Unknown path components: /me"

    That second message is the tell: Meta did not recognise the version prefix,
    so it read "v29.0" as a node name and /me as an unknown edge under it.
    Matching 'invalid version' instead (as this did until 2026-08-25) matched
    nothing ever, so every probe looked live and 'latest' was always
    current + MAX_PROBE_AHEAD."""
    status, body = call(version, "me", token="", fields="id")
    msg = (body.get("error") or {}).get("message", "")
    if status == 0:  # transport/TLS failure: no answer, so claim nothing
        print(f"::warning::could not probe {version} ({msg}) — treating it as unreleased")
        return False
    return not re.search(r"unknown path components|invalid version|unsupported.{0,20}version",
                         msg, re.I)


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
        # Meta's versions are contiguous: stop at the first gap instead of
        # taking the highest hit, so one bad probe cannot invent a version.
        if not version_exists(f"v{probe}.0"):
            break
        latest_major = probe
    if latest_major == current_major + MAX_PROBE_AHEAD:
        print(f"::warning::probe ceiling hit ({MAX_PROBE_AHEAD} ahead) — "
              "latest may be underreported, raise MAX_PROBE_AHEAD")
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
