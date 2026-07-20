# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] — 2026-07-19 (Edge fork)

Multi-account fork of [`AleemHaider/instagram-mcp`](https://github.com/AleemHaider/instagram-mcp)
by Claudia Chez.

### Added

- **Multi-account support** via `IG_ACCOUNTS` (JSON map of alias → account), a file at
  `~/.instagram-mcp/accounts.json` (`IG_ACCOUNTS_FILE` override), or legacy single-account env.
  Every tool takes an `account` alias.
- **8 Facebook Page tools** (`fb_publish_post`, `fb_publish_video`, `fb_list_posts`,
  `fb_list_comments`, `fb_reply_to_comment`, `fb_hide_comment`, `fb_delete_comment`,
  `fb_page_insights`), plus `list_accounts` and a `health_check` diagnostics tool.
- A **Claude plugin** (`instagram-social`) with a guided `connect-meta-account` onboarding
  skill and a robust `uvx` launcher; a `.mcpb` Desktop bundle built in CI; a weekly Graph API
  **version watchdog**.
- `SECURITY.md`, plus Privacy/data-handling and uninstall documentation.

### Fixed / hardened

- Access tokens no longer leak into server logs (httpx request logging suppressed).
- Actionable errors + `health_check` for the remote-sandbox/scope failure mode.
- `uvx` resolved under the minimal GUI PATH; zsh-safe setup snippets; accented names
  transliterated into aliases (e.g. "Ágora" → `agora`).

## [0.1.1] — 2026-05-13

### Fixed

- Correct GitHub repository URLs in package metadata (was pointing at a
  non-existent owner in the 0.1.0 wheel).

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

[0.1.1]: https://github.com/AleemHaider/instagram-mcp/releases/tag/v0.1.1
[0.1.0]: https://github.com/AleemHaider/instagram-mcp/releases/tag/v0.1.0
