#!/usr/bin/env bash
# SessionStart nudge for the Instagram Social plugin.
# Stays silent once at least one account is configured; otherwise briefs Claude
# to offer the guided setup. Never prints tokens or secrets.
set -euo pipefail

CFG="${HOME}/.instagram-mcp/accounts.json"

if [ -n "${IG_ACCOUNTS:-}" ] || [ -f "$CFG" ]; then
  exit 0
fi

cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"The Instagram Social plugin is installed but no accounts are connected yet. If the user wants to post to or manage Instagram or Facebook Pages, offer to run the guided setup skill 'connect-accounts' to connect their first account."}}
JSON
