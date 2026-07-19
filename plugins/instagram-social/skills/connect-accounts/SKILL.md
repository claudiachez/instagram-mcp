---
name: connect-accounts
description: Guide the user through connecting an Instagram Business/Creator or Facebook Page account so the Instagram tools work. Use when the user wants to set up, add, connect, or onboard an Instagram or Facebook account, mentions IG_ACCOUNTS, sees a "no accounts configured" error, or asks how to make the Instagram/Facebook tools work.
---

# Connect an Instagram / Facebook account

Walk a possibly non-technical user through connecting one or more accounts so the
Instagram and Facebook Page tools work. Be friendly, do one step at a time, and
confirm each step before moving on. Each account takes about 2 minutes.

## Before you start
- The user needs access to the **Meta app** for this tool — its **App ID** and
  **App Secret**. If they don't have these, tell them to ask their admin (and that
  the admin must add them to the Meta app before their keys will work).
- The MCP server runs via `uvx`, so **`uv`** must be installed. Check with
  `uv --version`; if it's missing, point them to
  https://docs.astral.sh/uv/getting-started/installation/ and help them install it.

## Steps

1. **Set expectations.** Tell them you'll create one permanent key per account and
   it takes ~2 minutes each. Nothing here is destructive.

2. **Get a short-lived token.** Ask them to:
   - Open the Graph API Explorer: https://developers.facebook.com/tools/explorer
   - Top-right: select their app, and set token type to **User Token**.
   - Add these 7 permissions, then click **Generate Access Token**, log in, choose
     the Pages they manage, and **Continue**:
     `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`,
     `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`,
     `business_management`
   - Copy the token. It's short-lived (~1 hour) — that's fine.

3. **Exchange it for permanent keys.** Ask for their **App ID**, **App Secret**, and
   the **short-lived token** from step 2. Then, if you can run shell commands, do the
   exchange for them with `curl` (if you cannot run shell commands, give them these
   exact commands to run and have the *command itself* write the file in step 4 — do
   not ask them to paste tokens back into the chat):
   - Long-lived user token:
     `curl -sG "https://graph.facebook.com/v21.0/oauth/access_token" --data-urlencode "grant_type=fb_exchange_token" --data-urlencode "client_id=APP_ID" --data-urlencode "client_secret=APP_SECRET" --data-urlencode "fb_exchange_token=SHORT_TOKEN"`
   - Pages + linked IG accounts + never-expiring Page tokens:
     `curl -sG "https://graph.facebook.com/v21.0/me/accounts" --data-urlencode "fields=id,name,instagram_business_account{id,username},access_token" --data-urlencode "access_token=LONG_USER_TOKEN"`
   - For each account the user wants, capture three values from the response: the
     Page's `access_token` (the permanent **token**), `instagram_business_account.id`
     (the **user_id**), and the Page `id` (the **fb_page_id**).

4. **Save it.** Write/merge the account into `~/.instagram-mcp/accounts.json`, creating
   the folder and file if needed. It's a JSON object mapping a short **alias** (agree on
   one with the user — lowercase brand name, no spaces) to the account. Merge with any
   existing entries; never overwrite other accounts. Shape:
   ```json
   {
     "brand_a": {"user_id": "17841...", "token": "EAA...", "fb_page_id": "10x..."}
   }
   ```
   `fb_page_id` is optional — include it whenever you have it so Facebook Page tools work.

5. **Confirm.** Run the `list_accounts` tool and show the user their connected accounts
   by **username only** — never tokens. If their account appears, it's connected.

6. **Offer to add another.** The same short-lived token works for all their Pages for
   about an hour, so repeat from step 2 for each additional account.

## Rules
- **Never** print tokens, the App Secret, or the raw contents of `accounts.json` back to
  the user or into the conversation. When showing accounts, show usernames/aliases only.
- If an account has no linked Instagram account, save it anyway with its `fb_page_id` —
  the Facebook Page tools will still work for it.
- After saving, the user may need to restart their Claude app (or reload the plugin) for
  the server to pick up the new accounts.
