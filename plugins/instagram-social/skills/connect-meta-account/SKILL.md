---
name: connect-meta-account
description: Guide the user through connecting an Instagram Business/Creator account (and its Facebook Page) so the Instagram/Facebook tools work. Use when the user wants to set up, add, connect, or onboard an Instagram or Facebook account, sees a "no accounts configured" error, mentions IG_ACCOUNTS, or asks how to make the tools work.
---

# Connect an Instagram / Facebook account

Walk a possibly non-technical user through connecting one or more accounts so the
Instagram and Facebook Page tools work. Be friendly, do ONE step at a time, explain
jargon in plain terms, and confirm each step before moving on. ~2–7 minutes total.

## Step 0 — Make sure they have a Meta app (ASK FIRST, then branch)

This tool talks to Instagram/Facebook through a **developer app on Meta's platform**
(registered at developers.facebook.com) — think of it as the software key that lets the
tool act on your accounts. It's identified by an **App ID** (public) and **App Secret**
(private password).

**Ask the user which of these is true, and branch — don't make them do steps they don't need:**

- **"I already have a Meta app (App ID + App Secret)."** → Great, skip to **Step 1**.
- **"My team/organization has one."** → They ask their admin for the **App ID + App Secret**,
  and the admin must **add them to the app** first (App roles → add as developer or tester),
  or the keys won't authenticate. Then go to **Step 1**.
- **"I don't have one."** → Walk them through creating their own (free, ~5 min) below, then
  go to **Step 1**.

### Creating a Meta app (only if they don't have one)

1. Go to https://developers.facebook.com/apps → **Create app**.
2. **Use case: Other** → Next → **App type: Business** → Next.
3. Name it (e.g. "My Social Manager"), add their email, optionally attach a Business
   portfolio → **Create app**. (Meta may re-prompt for their Facebook password — that's normal.)
4. In the dashboard: **Add product → Instagram → Set up**, then choose
   **"API setup with Facebook login"** (the Graph API path — NOT Basic Display).
5. Leave the app in **Development mode**. That's fine — as the app's own admin they get full
   access to their own accounts; no Meta App Review is needed for personal/internal use.
6. Copy the **App ID** and **App Secret** from **App settings → Basic** (App Secret is behind
   a "Show" button).

## Step 1 — Get a short-lived token

Ask them to:
- Open the Graph API Explorer: https://developers.facebook.com/tools/explorer
- Top-right: select their app, set token type to **User Token**.
- Add these 7 permissions, click **Generate Access Token**, log in, choose the Pages they
  manage, and **Continue** (add `instagram_manage_messages` too if they want DMs):
  `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`,
  `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`,
  `business_management`
- Copy the token (short-lived, ~1 hour — fine).

## Step 2 — Exchange it for permanent keys

Collect the **App ID**, **App Secret**, and **short-lived token** by **asking in chat**, then
substitute them directly into the `curl` commands below. Do **NOT** use interactive shell
prompts like `read -p "..."` — that fails on zsh (the macOS default) with `read: -p: no
coprocess`, silently leaving variables empty. If you must read from the shell, use `read -r VAR`
(and `read -rs VAR` for secrets). If you can run shell commands, do the exchange with `curl`
(otherwise give them the exact commands and have the command itself write the file in Step 3 —
never ask them to paste tokens back into the chat):
- Long-lived user token:
  `curl -sG "https://graph.facebook.com/v21.0/oauth/access_token" --data-urlencode "grant_type=fb_exchange_token" --data-urlencode "client_id=APP_ID" --data-urlencode "client_secret=APP_SECRET" --data-urlencode "fb_exchange_token=SHORT_TOKEN"`
- Pages + linked IG accounts + never-expiring Page tokens:
  `curl -sG "https://graph.facebook.com/v21.0/me/accounts" --data-urlencode "fields=id,name,instagram_business_account{id,username},access_token" --data-urlencode "access_token=LONG_USER_TOKEN"`
- For each account, capture: the Page's `access_token` (permanent **token**),
  `instagram_business_account.id` (the **user_id**), and the Page `id` (**fb_page_id**).

## Step 3 — Save it

Write/merge the account into `~/.instagram-mcp/accounts.json` (create the folder/file if
needed). It maps a short **alias** to the account. Build the alias by **transliterating accents
to ASCII** (Á→a, ñ→n), lowercasing, and replacing runs of non-alphanumeric characters with `_`
— e.g. "Ágora Dominicana" → `agora_dominicana`. Do **NOT** just delete non-ASCII characters
(that turns "Ágora" into "gora"). Merge with existing entries; never overwrite others:
```json
{
  "brand_a": {"user_id": "17841...", "token": "EAA...", "fb_page_id": "10x..."}
}
```
`fb_page_id` is optional — include it whenever you have it so Facebook Page tools work.

## Step 4 — Confirm

Call the `list_accounts` MCP tool and show the user their connected accounts by
**username/alias only** — never tokens. If their account appears, it's connected. Then offer to
add another (the same short-lived token works for all their Pages for ~1 hour).

**Critical — how to verify, and how NOT to:** confirmation MUST come from calling the
`list_accounts` (or `health_check`) MCP tool. If those `instagram-social` tools are **not** in
your available tools, tell the user plainly: *"the plugin's server isn't loaded in this
session"* — suggest they run `health_check`, and check that the plugin is installed **locally**,
not only from the remote Directory (a remote/cloud install can't read files on their computer).
Do **NOT** inspect the filesystem yourself to "verify" the accounts file — your sandbox is not
the user's machine, so any `ls`/`cat` you run there is meaningless and will mislead everyone.

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
- After saving, the user may need to restart their Claude app (or reload the plugin) for the
  server to pick up new accounts.
