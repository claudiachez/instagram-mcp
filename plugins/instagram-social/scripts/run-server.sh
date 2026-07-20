#!/usr/bin/env bash
# Launch the instagram-social MCP server, resolving `uvx` even under the minimal
# PATH that Dock-launched macOS GUI apps get (which omits /opt/homebrew/bin on
# Apple Silicon and ~/.local/bin). See postmortem P7.
set -euo pipefail

find_uvx() {
  for d in "$HOME/.local/bin" /opt/homebrew/bin /usr/local/bin /usr/bin; do
    if [ -x "$d/uvx" ]; then
      printf '%s\n' "$d/uvx"
      return 0
    fi
  done
  command -v uvx 2>/dev/null && return 0
  return 1
}

if ! UVX="$(find_uvx)"; then
  echo "instagram-social: 'uvx' not found. Install uv (\`brew install uv\` or \`pip3 install uv\`)," \
       "then restart your Claude app." >&2
  exit 127
fi

exec "$UVX" --from "git+https://github.com/claudiachez/instagram-mcp.git" instagram-mcp "$@"
