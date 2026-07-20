# Security Policy

## Reporting a vulnerability

Please report security issues via a **private GitHub security advisory**:
<https://github.com/claudiachez/instagram-mcp/security/advisories/new>

For non-sensitive reports, a regular issue is fine:
<https://github.com/claudiachez/instagram-mcp/issues>

We aim to acknowledge reports within a few days.

## How credentials are handled

- Access tokens are supplied by **you** and stored only in a local file
  (`~/.instagram-mcp/accounts.json`) or the `IG_ACCOUNTS` environment variable.
- Tokens are **never** committed to the repository, **never** printed in tool output, and are
  kept out of logs (the HTTP client's request logging is suppressed so tokens don't reach the
  MCP server log).
- The server runs **locally over stdio** and makes outbound calls **only** to Meta's Graph API
  over HTTPS (`graph.facebook.com`). It opens no listening ports.

## Scope & trust model

- This is a community fork of [`AleemHaider/instagram-mcp`](https://github.com/AleemHaider/instagram-mcp)
  intended for personal/team use.
- The Meta app runs in **Development mode**: only accounts added to your app can authenticate,
  and each user brings their own app credentials. No secrets are embedded in this repository.
- Run the `health_check` tool at any time to confirm where the server is running and which
  files it can see (it never returns tokens).
