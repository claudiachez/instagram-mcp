# Instagram MCP — Edge IQ Fork Setup

Fork of `AleemHaider/instagram-mcp` (audited at v0.1.1, byte-identical PyPI↔GitHub)
with automated Graph API version management.

## How the automation keeps you ahead of Meta

**Three layers, proactive → defensive:**

1. **Weekly watchdog** (`version-watchdog.yml`, Mondays 12:00 UTC)
   - Probes Meta for newly released Graph API versions using your token
   - Smoke-tests the NEW version against your live IG account (read-only:
     profile fetch + media list) BEFORE proposing anything
   - New version + tests pass → opens a **pre-tested bump PR**
   - New version + tests fail → opens an issue flagging the breaking change,
     while your current version keeps working
   - Also smoke-tests your CURRENT default weekly — if Meta breaks/sunsets it,
     you get an 🚨 URGENT issue the same week, with the fix in the issue body
   - ≥3 versions behind → escalation issue (sunset window closing)

2. **Auto-rebuild** (`release-mcpb.yml`)
   - Merging the bump PR (or any code change) auto-builds a fresh `.mcpb`
     attached to a GitHub release. Update = download + drag into Claude Desktop.

3. **Hot override — the "never broken" escape hatch**
   - The `.mcpb` exposes *Graph API Version* as a settings field in Claude
     Desktop. If the default ever dies before you merge/rebuild, change one
     text field (e.g. `v21.0` → `v22.0`) and restart. No terminal, no rebuild,
     ~10 seconds. The URGENT issue tells you exactly what to type.

## One-time setup (Terminal, ~5 min)

Fork on GitHub first (or via gh CLI below), then:

```
gh repo fork AleemHaider/instagram-mcp --clone --org YOUR_GITHUB_USER
```

```
cd instagram-mcp
```

Copy this kit's files in (adjust source path):

```
cp -R /path/to/fork-kit/.github .
```

```
cp -R /path/to/fork-kit/scripts .
```

```
cp -R /path/to/fork-kit/mcpb .
```

```
git add -A && git commit -m "Add version watchdog + mcpb release automation" && git push
```

Add the two secrets the watchdog needs (Settings → Secrets → Actions, or):

```
gh secret set IG_ACCOUNTS
```

Paste the accounts JSON when prompted, e.g.
`{"edgeiq": {"user_id": "17841...", "token": "EAA...", "fb_page_id": "10x..."}}`
The watchdog smoke-tests EVERY account weekly, so a dead client token
surfaces as a Monday issue, not a failed campaign.

Trigger the first build:

```
gh workflow run release-mcpb.yml
```

Then download `instagram-mcp.mcpb` from the new release and drag into
Claude Desktop → Settings → Extensions. Enter your IG User ID + token in the
config panel (token stored as sensitive, never in code).

Sanity-check the watchdog immediately:

```
gh workflow run version-watchdog.yml
```

Green run = current version healthy, probe working. If Meta has already
shipped something past v21.0, expect a bump PR within a minute.

## Ongoing operation

- **Nothing to do weekly.** You only act when a PR or issue appears.
- Bump PR arrives → skim Meta's changelog link in the PR → merge → drag new
  `.mcpb` in. Total ~5 minutes, a few times per year.
- Keep the token secret fresh: Page tokens from the get-token flow are
  long-lived/non-expiring, but if you ever rotate it, update the GitHub
  secret AND the Claude Desktop config field.

## Merging upstream fixes (optional, deliberate)

```
git remote add upstream https://github.com/AleemHaider/instagram-mcp.git
```

```
git fetch upstream && git diff main upstream/main -- src/
```

Review the diff (the whole server is ~730 lines), then merge if clean:

```
git merge upstream/main
```
