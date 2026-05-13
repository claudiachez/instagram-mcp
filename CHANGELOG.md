# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-13

### Added

- Initial release.
- 24 MCP tools across five capability areas:
  - **Profile & media:** `get_my_profile`, `list_my_media`, `list_all_media`, `get_media`, `list_tagged_media`, `list_stories`
  - **Hashtags:** `search_hashtag`, `hashtag_top_media`, `hashtag_recent_media`
  - **Publishing:** `publish_image`, `publish_reel`, `publish_story`, `publish_carousel`, `get_publish_limit`
  - **Comments:** `list_comments`, `get_comment_replies`, `reply_to_comment`, `hide_comment`, `delete_comment`
  - **DMs:** `list_conversations`, `get_conversation`, `send_dm` (with optional `message_tag`)
  - **Insights:** `get_account_insights` (with `metric_type` support), `get_media_insights`
- Shared HTTP client with lazy initialization.
- Structured error responses (`{"error": True, "status", "message", "code", "subcode", "fbtrace_id"}`).
- Configurable Graph host (`graph.facebook.com` or `graph.instagram.com`).
- Pagination helper for media listings.
- Two-step container/publish flow with status polling for video/reels.
- `instagram-mcp-get-token` CLI helper to mint a long-lived Page token and write `.env`.

[0.1.0]: https://github.com/AleemHaider/instagram-mcp/releases/tag/v0.1.0
