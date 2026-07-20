"""Rebuild ~/.instagram-mcp/accounts.json for ALL Pages from ONE short-lived token.

Use this after resetting the Meta app secret (or any time you need to regenerate every
account at once). Unlike `instagram-mcp-get-token` (one account at a time, Instagram-linked
only), this captures every Page you manage — Instagram-linked AND Facebook-only — in a
single run, and never prints tokens.

Usage:
    instagram-mcp-rebuild-accounts
"""
from __future__ import annotations

import getpass
import json
import pathlib
import sys
import urllib.parse
import urllib.request

from .get_token import _slug

GRAPH = "https://graph.facebook.com/v21.0"


def _api(path: str, **params: str) -> dict:
    url = f"{GRAPH}/{path.lstrip('/')}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as r:
        body = json.loads(r.read())
    if "error" in body:
        raise SystemExit(f"Graph API error: {body['error']}")
    return body


def _prompt(label: str, secret: bool = False) -> str:
    val = (getpass.getpass(f"{label}: ") if secret else input(f"{label}: ")).strip()
    if not val:
        raise SystemExit(f"{label} is required")
    return val


def _build_accounts(pages: list[dict]) -> dict[str, dict]:
    """Turn /me/accounts Page objects into the IG_ACCOUNTS map. Instagram-linked Pages
    get a user_id + username-based alias; Facebook-only Pages get a name-based alias.
    Pages without an access_token (no admin rights) are skipped. Aliases are de-duped."""
    accounts: dict[str, dict] = {}
    for p in pages:
        token = p.get("access_token")
        if not token:
            continue
        ig = p.get("instagram_business_account")
        alias = _slug(ig["username"]) if ig else _slug(p.get("name", ""))
        base, n = alias, 2
        while alias in accounts:
            alias = f"{base}_{n}"
            n += 1
        if ig:
            accounts[alias] = {"user_id": ig["id"], "token": token, "fb_page_id": p["id"]}
        else:
            accounts[alias] = {"token": token, "fb_page_id": p["id"]}
    return accounts


def main() -> None:
    print("Instagram MCP — rebuild ALL accounts")
    print("=" * 40)
    print(
        "You'll need:\n"
        "  1. Your Meta App ID and the CURRENT App Secret (App Dashboard → Settings → Basic)\n"
        "  2. A fresh short-lived User Token from the Graph API Explorer with scopes:\n"
        "     instagram_basic, instagram_content_publish, instagram_manage_comments,\n"
        "     instagram_manage_insights, pages_show_list, pages_read_engagement,\n"
        "     business_management\n"
    )
    app_id = _prompt("App ID")
    app_secret = _prompt("App Secret", secret=True)
    short_token = _prompt("Short-lived user token", secret=True)

    print("\n[1/3] Exchanging for a long-lived user token...")
    long_user = _api(
        "oauth/access_token",
        grant_type="fb_exchange_token",
        client_id=app_id,
        client_secret=app_secret,
        fb_exchange_token=short_token,
    )["access_token"]
    print("      done.")

    print("[2/3] Listing every Page (Instagram-linked and Facebook-only)...")
    pages: list[dict] = []
    data = _api(
        "me/accounts",
        fields="id,name,instagram_business_account{id,username},access_token",
        access_token=long_user,
        limit="100",
    )
    pages.extend(data.get("data", []))
    nxt = data.get("paging", {}).get("next")
    while nxt:
        with urllib.request.urlopen(nxt) as r:
            page = json.loads(r.read())
        pages.extend(page.get("data", []))
        nxt = page.get("paging", {}).get("next")

    accounts = _build_accounts(pages)
    if not accounts:
        raise SystemExit("No Pages with admin access found for this token.")

    print("[3/3] Writing ~/.instagram-mcp/accounts.json...")
    cfg_dir = pathlib.Path.home() / ".instagram-mcp"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    path = cfg_dir / "accounts.json"
    if path.exists():
        backup = path.with_suffix(".json.bak")
        backup.write_text(path.read_text())
        print(f"      existing file backed up to {backup}")
    path.write_text(json.dumps(accounts, indent=2))
    print(f"      wrote {len(accounts)} accounts to {path}")

    ig = sorted(a for a, v in accounts.items() if v.get("user_id"))
    fb_only = sorted(a for a, v in accounts.items() if not v.get("user_id"))
    print(f"\n  Instagram + Facebook ({len(ig)}): {', '.join(ig)}")
    print(f"  Facebook Page only  ({len(fb_only)}): {', '.join(fb_only)}")
    print("\nAll set. Restart your Claude app, then run the `health_check` tool to confirm.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\naborted.", file=sys.stderr)
        sys.exit(130)
