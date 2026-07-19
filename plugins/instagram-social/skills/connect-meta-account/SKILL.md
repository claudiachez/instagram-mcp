---
name: connect-meta-account
description: Guide the user through connecting an Instagram Business/Creator account (and its Facebook Page) so the Instagram/Facebook tools work. Use when the user wants to set up, add, connect, or onboard an Instagram or Facebook account, sees a "no accounts configured" error, mentions IG_ACCOUNTS, or asks how to make the tools work.
---

# Connect an Instagram / Facebook account

Walk a possibly non-technical user through connecting one or more accounts so the
Instagram and Facebook Page tools work. Be friendly, do one step at a time, explain
jargon in plain terms, and confirm each step before moving on. ~2 minutes per account.

## First, explain what's needed (in plain terms)

This tool talks to Instagram and Facebook through a **developer app on Meta's platform**
— the "app" someone on the team registered at developers.facebook.com. Think of it as the
software key that lets this tool act on your accounts. Two values identify it:

- **App ID** — a public number that names the app.
- **App Secret** — a private password for the app (treat it like a password).

Tell the user:
- If **they** set up this tool, they already have these — in the Meta developer dashboard
  under **App settings → Basic** (the App Secret is behind a "Show" button).
- If a **teammate/admin** set it up, they should ask that person for the App ID and App
  Secret — **and** the admin must first **add them to the app** (as a developer or tester),
  or the keys won't authenticate.

Also confirm the runtime `uv` is installed (see "Installing uv" at the bottom).

## Steps

1. **Set expectations.** One permanent key per account, ~2 minutes each, nothing destructive.

2. **Get a short-lived token.** Ask them to:
   - Open the Graph API Explorer: https://developers.facebook.com/tools/explorer
   - Top-right: select their app, set token type to **User Token**.
   - Add these 7 permissions, click **Generate Access Token**, log in, choose the Pages
     they manage, and **Continue** (add `instagram_manage_messages` too if they want DMs):
     `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`,
     `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`,
     `business_management`
   - Copy the token (short-lived, ~1 hour — fine).

3. **Exchange it for permanent keys.** Ask for their **App ID**, **App Secret**, and the
   **short-lived token**. If you can run shell commands, do the exchange with `curl`
   (otherwise give them the exact commands and have the command itself write the file in
   step 4 — never ask them to paste tokens back into the chat):
   - Long-lived user token:
     `curl -sG "https://graph.facebook.com/v21.0/oauth/access_token" --data-urlencode "grant_type=fb_exchange_token" --data-urlencode "client_id=APP_ID" --data-urlencode "client_secret=APP_SECRET" --data-urlencode "fb_exchange_token=SHORT_TOKEN"`
   - Pages + linked IG accounts + never-expiring Page tokens:
     `curl -sG "https://graph.facebook.com/v21.0/me/accounts" --data-urlencode "fields=id,name,instagram_business_account{id,username},access_token" --data-urlencode "access_token=LONG_USER_TOKEN"`
   - For each account, capture: the Page's `access_token` (permanent **token**),
     `instagram_business_account.id` (the **user_id**), and the Page `id` (**fb_page_id**).

4. **Save it.** Write/merge the account into `~/.instagram-mcp/accounts.json` (create the
   folder/file if needed). It maps a short **alias** (agree on one — lowercase brand name,
   no spaces) to the account. Merge with existing entries; never overwrite others:
   ```json
   {
     "brand_a": {"user_id": "17841...", "token": "EAA...", "fb_page_id": "10x..."}
   }
   ```
   `fb_page_id` is optional — include it whenever you have it so Facebook Page tools work.

5. **Confirm.** Run the `list_accounts` tool and show the user their connected accounts by
   **username/alias only** — never tokens. If their account appears, it's connected.

6. **Offer to add another.** The same short-lived token works for all their Pages for ~1
   hour, so repeat from step 2 per account.

## Installing uv (one-time, if missing)

The server runs via `uv`. Offer whichever source the user trusts:
- **Homebrew (Mac):** `brew install uv`
- **Python / pip:** `pip3 install uv`  (or `pipx install uv`)
- uv's official installer (made by Astral, the team behind the Ruff linter): https://docs.astral.sh/uv/
- **No install at all:** use the **Claude Desktop extension (`.mcpb`)** instead — it bundles
  everything and needs no `uv`. Point wary or non-technical users here.

## Rules
- **Never** print tokens, the App Secret, or the raw contents of `accounts.json` into the
  conversation. Show usernames/aliases only.
- If an account has no linked Instagram account, still save it with its `fb_page_id` — the
  Facebook Page tools will work for it.
- After saving, the user may need to restart their Claude app (or reload the plugin) for
  the server to pick up new accounts.
