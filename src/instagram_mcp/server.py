from __future__ import annotations

import asyncio
import functools
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from . import graph
from .graph import GraphError, fb_page_id, ig_user_id

load_dotenv()

mcp = FastMCP("instagram-mcp")

DEFAULT_PROFILE_FIELDS = (
    "id,username,name,biography,followers_count,follows_count,"
    "media_count,profile_picture_url,website"
)
DEFAULT_MEDIA_FIELDS = (
    "id,caption,media_type,media_product_type,media_url,thumbnail_url,"
    "permalink,timestamp,like_count,comments_count"
)
DEFAULT_HASHTAG_MEDIA_FIELDS = (
    "id,caption,media_type,permalink,timestamp,like_count,comments_count"
)

# Every tool takes `account` first: an alias from IG_ACCOUNTS. It may be omitted
# when exactly one account is configured (it then resolves to that sole account).

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def tool(fn: F) -> F:
    """Register an MCP tool, mapping GraphError / ValueError into a structured dict."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except GraphError as e:
            return e.to_dict()
        except (ValueError, TypeError) as e:
            return {"error": True, "message": str(e), "type": type(e).__name__}

    return mcp.tool()(wrapper)  # type: ignore[return-value]


# ---------- Accounts ----------

@tool
async def list_accounts() -> dict[str, Any]:
    """List configured account aliases with their IG user IDs, FB Page IDs, and
    live-fetched IG usernames. Never returns tokens."""
    accounts: list[dict[str, Any]] = []
    for alias in graph.account_aliases():
        info = graph.account_info(alias)
        entry: dict[str, Any] = {
            "alias": alias,
            "user_id": info["user_id"],
            "fb_page_id": info["fb_page_id"],
        }
        if info["user_id"]:
            try:
                prof = await graph.get(info["user_id"], account=alias, fields="username")
                entry["username"] = prof.get("username")
            except GraphError as e:
                entry["username_error"] = e.to_dict()["message"]
        accounts.append(entry)
    return {"accounts": accounts}


# ---------- Profile & media ----------

@tool
async def get_my_profile(
    account: str | None = None, *, fields: str | None = None
) -> dict[str, Any]:
    """Profile info for the configured Instagram Business/Creator account (`account` alias)."""
    return await graph.get(
        ig_user_id(account), account=account, fields=fields or DEFAULT_PROFILE_FIELDS
    )


@tool
async def list_my_media(
    account: str | None = None,
    *,
    limit: int = 25,
    after: str | None = None,
    fields: str | None = None,
) -> dict[str, Any]:
    """List one page of recent media for `account`. `after` is the paging cursor
    from a prior response."""
    return await graph.get(
        f"{ig_user_id(account)}/media",
        account=account,
        fields=fields or DEFAULT_MEDIA_FIELDS,
        limit=limit,
        after=after,
    )


@tool
async def list_all_media(
    account: str | None = None,
    *,
    max_pages: int = 5,
    fields: str | None = None,
) -> dict[str, Any]:
    """Walk media pages for `account` up to max_pages (default 5 = up to ~125 items)."""
    return await graph.paginate(
        f"{ig_user_id(account)}/media",
        account=account,
        max_pages=max_pages,
        fields=fields or DEFAULT_MEDIA_FIELDS,
    )


@tool
async def get_media(
    account: str | None = None, *, media_id: str, fields: str | None = None
) -> dict[str, Any]:
    """Fetch one media item by ID for `account`."""
    return await graph.get(media_id, account=account, fields=fields or DEFAULT_MEDIA_FIELDS)


@tool
async def list_tagged_media(
    account: str | None = None, *, limit: int = 25, fields: str | None = None
) -> dict[str, Any]:
    """List media the `account` is tagged in."""
    return await graph.get(
        f"{ig_user_id(account)}/tags",
        account=account,
        fields=fields or DEFAULT_MEDIA_FIELDS,
        limit=limit,
    )


@tool
async def list_stories(account: str | None = None) -> dict[str, Any]:
    """List the `account`'s currently-live stories (expire after 24h)."""
    return await graph.get(
        f"{ig_user_id(account)}/stories",
        account=account,
        fields="id,media_type,media_url,permalink,timestamp",
    )


# ---------- Hashtags ----------

@tool
async def search_hashtag(account: str | None = None, *, query: str) -> dict[str, Any]:
    """Resolve a hashtag string to an IG hashtag ID (queried as `account`)."""
    return await graph.get(
        "ig_hashtag_search", account=account, user_id=ig_user_id(account), q=query.lstrip("#")
    )


@tool
async def hashtag_top_media(
    account: str | None = None, *, hashtag_id: str, fields: str | None = None
) -> dict[str, Any]:
    """Top-ranked media for a hashtag (queried as `account`)."""
    return await graph.get(
        f"{hashtag_id}/top_media",
        account=account,
        user_id=ig_user_id(account),
        fields=fields or DEFAULT_HASHTAG_MEDIA_FIELDS,
    )


@tool
async def hashtag_recent_media(
    account: str | None = None, *, hashtag_id: str, fields: str | None = None
) -> dict[str, Any]:
    """Recent media for a hashtag, rolling 24h window (queried as `account`)."""
    return await graph.get(
        f"{hashtag_id}/recent_media",
        account=account,
        user_id=ig_user_id(account),
        fields=fields or DEFAULT_HASHTAG_MEDIA_FIELDS,
    )


# ---------- Publishing ----------

async def _wait_container(account: str | None, container_id: str, timeout_s: int = 300) -> None:
    """Poll a media container until status_code=FINISHED. Required for video/reels."""
    elapsed = 0
    while elapsed < timeout_s:
        res = await graph.get(container_id, account=account, fields="status_code,status")
        code = res.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise GraphError(
                0,
                {"error": {"message": f"container {container_id} status={code}", "code": -1}},
            )
        await asyncio.sleep(3)
        elapsed += 3
    raise TimeoutError(f"container {container_id} did not finish within {timeout_s}s")


async def _publish(account: str | None, container_id: str) -> dict[str, Any]:
    return await graph.post(
        f"{ig_user_id(account)}/media_publish", account=account, creation_id=container_id
    )


@tool
async def publish_image(
    account: str | None = None,
    *,
    image_url: str,
    caption: str | None = None,
    location_id: str | None = None,
) -> dict[str, Any]:
    """Publish a single image post for `account`. image_url must be a public HTTPS URL."""
    container = await graph.post(
        f"{ig_user_id(account)}/media",
        account=account,
        image_url=image_url,
        caption=caption,
        location_id=location_id,
    )
    return await _publish(account, container["id"])


@tool
async def publish_reel(
    account: str | None = None,
    *,
    video_url: str,
    caption: str | None = None,
    share_to_feed: bool = True,
    cover_url: str | None = None,
    thumb_offset: int | None = None,
) -> dict[str, Any]:
    """Publish a Reel for `account`. video_url must be a public HTTPS MP4."""
    container = await graph.post(
        f"{ig_user_id(account)}/media",
        account=account,
        media_type="REELS",
        video_url=video_url,
        caption=caption,
        share_to_feed=str(share_to_feed).lower(),
        cover_url=cover_url,
        thumb_offset=thumb_offset,
    )
    await _wait_container(account, container["id"])
    return await _publish(account, container["id"])


@tool
async def publish_story(
    account: str | None = None,
    *,
    image_url: str | None = None,
    video_url: str | None = None,
) -> dict[str, Any]:
    """Publish a Story for `account`. Provide exactly one of image_url or video_url."""
    if bool(image_url) == bool(video_url):
        raise ValueError("Provide exactly one of image_url or video_url")
    container = await graph.post(
        f"{ig_user_id(account)}/media",
        account=account,
        media_type="STORIES",
        image_url=image_url,
        video_url=video_url,
    )
    if video_url:
        await _wait_container(account, container["id"])
    return await _publish(account, container["id"])


@tool
async def publish_carousel(
    account: str | None = None,
    *,
    items: list[dict[str, str]],
    caption: str | None = None,
) -> dict[str, Any]:
    """Publish a 2-10 item carousel for `account`. Each item is {image_url: "..."}
    or {video_url: "..."}."""
    if not 2 <= len(items) <= 10:
        raise ValueError("Carousel must contain between 2 and 10 items")

    child_ids: list[str] = []
    for item in items:
        if "image_url" in item:
            child = await graph.post(
                f"{ig_user_id(account)}/media",
                account=account,
                is_carousel_item="true",
                image_url=item["image_url"],
            )
        elif "video_url" in item:
            child = await graph.post(
                f"{ig_user_id(account)}/media",
                account=account,
                is_carousel_item="true",
                media_type="VIDEO",
                video_url=item["video_url"],
            )
            await _wait_container(account, child["id"])
        else:
            raise ValueError(f"Carousel item must contain image_url or video_url: {item}")
        child_ids.append(child["id"])

    parent = await graph.post(
        f"{ig_user_id(account)}/media",
        account=account,
        media_type="CAROUSEL",
        children=",".join(child_ids),
        caption=caption,
    )
    return await _publish(account, parent["id"])


@tool
async def get_publish_limit(account: str | None = None) -> dict[str, Any]:
    """Show publish quota usage for `account` in the rolling 24h window."""
    return await graph.get(
        f"{ig_user_id(account)}/content_publishing_limit",
        account=account,
        fields="quota_usage,config",
    )


# ---------- Comments ----------

@tool
async def list_comments(
    account: str | None = None, *, media_id: str, limit: int = 25
) -> dict[str, Any]:
    """List top-level comments on a media item, including their replies (`account` alias)."""
    return await graph.get(
        f"{media_id}/comments",
        account=account,
        fields="id,text,username,timestamp,like_count,replies{id,text,username,timestamp}",
        limit=limit,
    )


@tool
async def get_comment_replies(
    account: str | None = None, *, comment_id: str, limit: int = 25
) -> dict[str, Any]:
    """Fetch replies under a specific comment (`account` alias)."""
    return await graph.get(
        f"{comment_id}/replies",
        account=account,
        fields="id,text,username,timestamp,like_count",
        limit=limit,
    )


@tool
async def reply_to_comment(
    account: str | None = None, *, comment_id: str, message: str
) -> dict[str, Any]:
    """Reply to a comment (`account` alias)."""
    return await graph.post(f"{comment_id}/replies", account=account, message=message)


@tool
async def hide_comment(
    account: str | None = None, *, comment_id: str, hide: bool = True
) -> dict[str, Any]:
    """Hide (or unhide) a comment (`account` alias)."""
    return await graph.post(comment_id, account=account, hide=str(hide).lower())


@tool
async def delete_comment(account: str | None = None, *, comment_id: str) -> dict[str, Any]:
    """Delete a comment owned by the `account`."""
    return await graph.delete(comment_id, account=account)


# ---------- Direct messages ----------

@tool
async def list_conversations(account: str | None = None, *, limit: int = 20) -> dict[str, Any]:
    """List Instagram DM conversations for the `account`."""
    return await graph.get(
        f"{ig_user_id(account)}/conversations",
        account=account,
        platform="instagram",
        fields="id,updated_time,participants",
        limit=limit,
    )


@tool
async def get_conversation(
    account: str | None = None, *, conversation_id: str, message_limit: int = 25
) -> dict[str, Any]:
    """Fetch messages in a conversation (`account` alias)."""
    return await graph.get(
        conversation_id,
        account=account,
        fields=f"messages.limit({message_limit}){{id,created_time,from,to,message}}",
    )


@tool
async def send_dm(
    account: str | None = None,
    *,
    recipient_igsid: str,
    text: str,
    message_tag: str | None = None,
) -> dict[str, Any]:
    """Send a DM from `account`. Without a tag this is `RESPONSE` (only valid inside
    the 24h user-initiated window). Pass message_tag (e.g. HUMAN_AGENT) to escape that
    window — requires Meta approval for the tag."""
    payload: dict[str, Any] = {
        "recipient": json.dumps({"id": recipient_igsid}),
        "message": json.dumps({"text": text}),
    }
    if message_tag:
        payload["messaging_type"] = "MESSAGE_TAG"
        payload["tag"] = message_tag
    else:
        payload["messaging_type"] = "RESPONSE"
    return await graph.post(f"{ig_user_id(account)}/messages", account=account, **payload)


# ---------- Insights ----------

@tool
async def get_account_insights(
    account: str | None = None,
    *,
    metrics: str = "reach,follower_count",
    period: str = "day",
    metric_type: str | None = None,
    since: int | None = None,
    until: int | None = None,
) -> dict[str, Any]:
    """Account-level insights for `account`. Modern metrics (views, accounts_engaged,
    total_interactions, profile_views, likes, comments, shares, saves) require
    metric_type='total_value'."""
    return await graph.get(
        f"{ig_user_id(account)}/insights",
        account=account,
        metric=metrics,
        period=period,
        metric_type=metric_type,
        since=since,
        until=until,
    )


@tool
async def get_media_insights(
    account: str | None = None,
    *,
    media_id: str,
    metrics: str = "reach,saved,likes,comments,shares",
) -> dict[str, Any]:
    """Insights for a single media item (`account` alias). Valid metric set varies by
    media type (post / reel / story)."""
    return await graph.get(f"{media_id}/insights", account=account, metric=metrics)


# ---------- Facebook Page ----------
# Same Page token as the account; endpoints target the account's fb_page_id.

@tool
async def fb_publish_post(
    account: str | None = None,
    *,
    message: str | None = None,
    link: str | None = None,
    photo_url: str | None = None,
) -> dict[str, Any]:
    """Publish a post to the `account`'s Facebook Page. With photo_url, publishes a
    photo (message becomes its caption); otherwise a text and/or link status."""
    page = fb_page_id(account)
    if photo_url:
        return await graph.post(f"{page}/photos", account=account, url=photo_url, caption=message)
    if not (message or link):
        raise ValueError("Provide message and/or link (or photo_url) to publish")
    return await graph.post(f"{page}/feed", account=account, message=message, link=link)


@tool
async def fb_publish_video(
    account: str | None = None,
    *,
    video_url: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Publish a video to the `account`'s Facebook Page. video_url must be a public HTTPS URL."""
    page = fb_page_id(account)
    return await graph.post(
        f"{page}/videos", account=account, file_url=video_url, description=description
    )


@tool
async def fb_list_posts(account: str | None = None, *, limit: int = 25) -> dict[str, Any]:
    """List recent posts on the `account`'s Facebook Page."""
    page = fb_page_id(account)
    return await graph.get(
        f"{page}/posts",
        account=account,
        fields="id,message,story,created_time,permalink_url",
        limit=limit,
    )


@tool
async def fb_list_comments(
    account: str | None = None, *, post_id: str, limit: int = 25
) -> dict[str, Any]:
    """List comments on a post on the `account`'s Facebook Page."""
    fb_page_id(account)
    return await graph.get(
        f"{post_id}/comments",
        account=account,
        fields="id,message,from,created_time,like_count,comment_count",
        limit=limit,
    )


@tool
async def fb_reply_to_comment(
    account: str | None = None, *, comment_id: str, message: str
) -> dict[str, Any]:
    """Reply to a comment on the `account`'s Facebook Page."""
    fb_page_id(account)
    return await graph.post(f"{comment_id}/comments", account=account, message=message)


@tool
async def fb_hide_comment(
    account: str | None = None, *, comment_id: str, hide: bool = True
) -> dict[str, Any]:
    """Hide (or unhide) a comment on the `account`'s Facebook Page."""
    fb_page_id(account)
    return await graph.post(comment_id, account=account, is_hidden=str(hide).lower())


@tool
async def fb_delete_comment(account: str | None = None, *, comment_id: str) -> dict[str, Any]:
    """Delete a comment on the `account`'s Facebook Page."""
    fb_page_id(account)
    return await graph.delete(comment_id, account=account)


@tool
async def fb_page_insights(
    account: str | None = None,
    *,
    metrics: str = "page_impressions,page_post_engagements",
    period: str = "day",
) -> dict[str, Any]:
    """Facebook Page insights for `account`. Returns the requested metrics for the period."""
    page = fb_page_id(account)
    return await graph.get(f"{page}/insights", account=account, metric=metrics, period=period)


def run() -> None:
    mcp.run()
