import pytest
import respx

from instagram_mcp import graph
from instagram_mcp.server import (
    get_account_insights,
    get_media,
    get_my_profile,
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
    result = await get_media("badid")
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


def test_missing_token_raises():
    import importlib
    import os
    os.environ.pop("IG_ACCESS_TOKEN", None)
    importlib.reload(graph)
    with pytest.raises(RuntimeError, match="IG_ACCESS_TOKEN"):
        graph._config()
