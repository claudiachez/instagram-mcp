import json

import pytest
import respx

from instagram_mcp import graph
from instagram_mcp.server import (
    fb_list_posts,
    fb_page_insights,
    get_account_insights,
    get_media,
    get_my_profile,
    health_check,
    mcp,
    publish_story,
)

BASE = "https://graph.facebook.com/v21.0"


async def test_all_tools_registered():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    expected = {
        "get_my_profile", "list_my_media", "list_all_media", "get_media",
        "list_tagged_media", "list_stories", "search_hashtag",
        "hashtag_top_media", "hashtag_recent_media", "publish_image",
        "publish_reel", "publish_story", "publish_carousel",
        "get_publish_limit", "list_comments", "get_comment_replies",
        "reply_to_comment", "hide_comment", "delete_comment",
        "list_conversations", "get_conversation", "send_dm",
        "get_account_insights", "get_media_insights",
        # multi-account + Facebook additions
        "list_accounts", "health_check", "fb_publish_post", "fb_publish_video",
        "fb_list_posts", "fb_list_comments", "fb_reply_to_comment", "fb_hide_comment",
        "fb_delete_comment", "fb_page_insights",
    }
    assert expected.issubset(names), expected - names


@respx.mock
async def test_get_my_profile_happy_path():
    respx.get(f"{BASE}/1234567890").respond(
        200,
        json={"id": "1234567890", "username": "test_account", "followers_count": 42},
    )
    result = await get_my_profile()
    assert result["username"] == "test_account"
    assert result["followers_count"] == 42


@respx.mock
async def test_graph_error_returns_structured_dict():
    respx.get(f"{BASE}/badid").respond(
        400,
        json={
            "error": {
                "message": "Object does not exist",
                "code": 100,
                "error_subcode": 33,
                "fbtrace_id": "trace-abc",
            }
        },
    )
    result = await get_media(media_id="badid")
    assert result == {
        "error": True,
        "status": 400,
        "message": "Object does not exist",
        "code": 100,
        "subcode": 33,
        "fbtrace_id": "trace-abc",
    }


async def test_value_error_returns_structured_dict():
    result = await publish_story()
    assert result["error"] is True
    assert result["type"] == "ValueError"
    assert "exactly one" in result["message"]


@respx.mock
async def test_none_params_are_dropped():
    """Ensure get_account_insights doesn't pass `since=None` to the API."""
    route = respx.get(f"{BASE}/1234567890/insights").respond(200, json={"data": []})
    await get_account_insights(metrics="reach", period="day")
    sent = dict(route.calls.last.request.url.params)
    assert "since" not in sent
    assert "until" not in sent
    assert "metric_type" not in sent
    assert sent["metric"] == "reach"
    assert sent["access_token"] == "test-token"


# ---------- Multi-account ----------

@respx.mock
async def test_single_account_default_resolves():
    """With one account configured (conftest's IG_USER_ID/IG_ACCESS_TOKEN),
    omitting `account` resolves to that sole account."""
    assert graph.account_aliases() == ["default"]
    respx.get(f"{BASE}/1234567890").respond(200, json={"id": "1234567890", "username": "solo"})
    result = await get_my_profile()  # no account arg
    assert result["username"] == "solo"


async def test_unknown_alias_error_lists_aliases_never_tokens(monkeypatch):
    monkeypatch.setenv(
        "IG_ACCOUNTS",
        json.dumps(
            {
                "brand_a": {"user_id": "111", "token": "secret-a"},
                "brand_b": {"user_id": "222", "token": "secret-b"},
            }
        ),
    )
    with pytest.raises(RuntimeError) as exc:
        graph._config("nope")
    msg = str(exc.value)
    assert "brand_b" in msg and "brand_a" in msg  # valid aliases surfaced
    assert "secret-a" not in msg and "secret-b" not in msg  # tokens never leaked

    # Ambiguous default (no account, multiple configured) also errors clearly.
    with pytest.raises(RuntimeError, match="Multiple accounts"):
        graph._config()


# ---------- Facebook Page ----------

@respx.mock
async def test_fb_page_insights_happy_path(monkeypatch):
    monkeypatch.setenv(
        "IG_ACCOUNTS",
        json.dumps({"brand_a": {"user_id": "111", "token": "page-tok", "fb_page_id": "99001"}}),
    )
    route = respx.get(f"{BASE}/99001/insights").respond(
        200, json={"data": [{"name": "page_impressions", "values": [{"value": 5}]}]}
    )
    result = await fb_page_insights("brand_a", metrics="page_impressions", period="day")
    assert result["data"][0]["name"] == "page_impressions"
    sent = dict(route.calls.last.request.url.params)
    assert sent["metric"] == "page_impressions"
    assert sent["access_token"] == "page-tok"  # the account's Page token was used


async def test_fb_tool_requires_fb_page_id(monkeypatch):
    """An alias without fb_page_id errors clearly when an FB tool is used."""
    monkeypatch.setenv(
        "IG_ACCOUNTS", json.dumps({"brand_a": {"user_id": "111", "token": "t"}})
    )
    with pytest.raises(RuntimeError, match="fb_page_id"):
        await fb_list_posts("brand_a")


def test_accounts_from_config_file(monkeypatch, tmp_path):
    """With no IG_ACCOUNTS env var, accounts load from the JSON file the guided
    setup writes (path via IG_ACCOUNTS_FILE, else ~/.instagram-mcp/accounts.json)."""
    monkeypatch.delenv("IG_ACCOUNTS", raising=False)
    monkeypatch.delenv("IG_USER_ID", raising=False)
    monkeypatch.delenv("IG_ACCESS_TOKEN", raising=False)
    cfg = tmp_path / "accounts.json"
    cfg.write_text(json.dumps({"brand_a": {"user_id": "1", "token": "t", "fb_page_id": "9"}}))
    monkeypatch.setenv("IG_ACCOUNTS_FILE", str(cfg))
    assert graph.account_aliases() == ["brand_a"]
    assert graph.ig_user_id("brand_a") == "1"
    assert graph.fb_page_id("brand_a") == "9"


async def test_health_check_reports_state_without_tokens(monkeypatch, tmp_path):
    cfg = tmp_path / "accounts.json"
    cfg.write_text(
        json.dumps({"brand_a": {"user_id": "1", "token": "secret-tok", "fb_page_id": "9"}})
    )
    monkeypatch.delenv("IG_ACCOUNTS", raising=False)
    monkeypatch.setenv("IG_ACCOUNTS_FILE", str(cfg))
    res = await health_check()
    assert res["account_count"] == 1
    assert res["aliases"] == ["brand_a"]
    assert res["accounts_file_exists"] is True
    assert res["account_source"].startswith("file:")
    assert "python" in res and "home" in res and "platform" in res
    assert "secret-tok" not in json.dumps(res)  # diagnostics never leak tokens


async def test_health_check_survives_no_accounts(monkeypatch, tmp_path):
    monkeypatch.delenv("IG_ACCOUNTS", raising=False)
    monkeypatch.delenv("IG_USER_ID", raising=False)
    monkeypatch.delenv("IG_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("IG_ACCOUNTS_FILE", str(tmp_path / "missing.json"))
    res = await health_check()  # must not raise
    assert res["account_count"] == 0
    assert res["accounts_file_exists"] is False
    assert res["account_source"] == "none"


@respx.mock
async def test_token_redacted_from_paging_urls():
    """Graph echoes the access_token inside paging next/previous URLs; those must be
    redacted before the response leaves a tool."""
    from instagram_mcp.server import list_comments
    respx.get(f"{BASE}/123/comments").respond(
        200,
        json={
            "data": [{"id": "1", "text": "hi"}],
            "paging": {"next": f"{BASE}/123/comments?access_token=test-token&after=X"},
        },
    )
    res = await list_comments(media_id="123")
    blob = json.dumps(res)
    assert "test-token" not in blob  # token never leaves in the response
    assert "REDACTED" in blob


def test_httpx_logging_suppressed_so_tokens_dont_hit_logs():
    import logging
    # graph sets these at import time; INFO-level httpx logs echo the URL (with the
    # access_token query param), so they must be raised to WARNING.
    assert logging.getLogger("httpx").level >= logging.WARNING
    assert logging.getLogger("httpcore").level >= logging.WARNING


def test_get_token_slug_transliterates():
    from instagram_mcp.scripts.get_token import _slug
    assert _slug("Ágora Dominicana") == "agora_dominicana"
    assert _slug("withjoy.dr") == "withjoy_dr"
    assert _slug("ñoño") == "nono"
    assert _slug("!!!") == "account"


def test_missing_token_raises():
    import importlib
    import os
    os.environ.pop("IG_ACCESS_TOKEN", None)
    importlib.reload(graph)
    with pytest.raises(RuntimeError, match="No accounts configured"):
        graph._config()
