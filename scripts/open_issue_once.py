#!/usr/bin/env python3
"""Open a GitHub issue unless an open one with the same title already exists.

Used by .github/workflows/version-watchdog.yml. Usage:

    open_issue_once.py "<title>" [--label L ...] <<'BODY'
    ... markdown with ${PLACEHOLDER} slots ...
    BODY

The body template is read from stdin and its ${...} slots are filled from the
environment (string.Template), so failure text containing quotes, newlines or
backticks never reaches a shell. Any real failure exits non-zero: a watchdog
that cannot report must go red instead of printing a reassuring message.
"""

import argparse
import json
import os
import subprocess
import sys
from string import Template

LABEL_MISSING = "not found"  # gh: "could not add label: 'urgent' not found"


def gh(*args: str) -> str:
    """Run gh, returning stdout. Raises RuntimeError with gh's own stderr."""
    proc = subprocess.run(["gh", *args], text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"gh {' '.join(args)} failed")
    return proc.stdout


def open_issues() -> list[str]:
    raw = gh("issue", "list", "--state", "open", "--limit", "200", "--json", "title")
    return [i["title"] for i in json.loads(raw)]


def create(title: str, body: str, labels: list[str]) -> str:
    cmd = ["issue", "create", "--title", title, "--body", body]
    for label in labels:
        cmd += ["--label", label]
    return gh(*cmd).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("title")
    ap.add_argument("--label", action="append", default=[], dest="labels")
    args = ap.parse_args()

    body = Template(sys.stdin.read()).safe_substitute(os.environ)

    # Match titles exactly instead of `gh issue list --search`: the search index
    # lags behind writes, which would let duplicates through.
    if args.title in open_issues():
        print(f"already reported, nothing to do: {args.title}")
        return 0

    try:
        print(create(args.title, body, args.labels))
        return 0
    except RuntimeError as e:
        if not (args.labels and LABEL_MISSING in str(e)):
            print(f"::error::could not open issue: {e}")
            return 1
        # Labels are cosmetic; the alert is not. Report anyway, then fail loudly
        # so the missing label gets fixed instead of silently swallowing alerts.
        print(f"::warning::label problem ({e}) — opening the issue without labels")
        try:
            print(create(args.title, body, []))
        except RuntimeError as e2:
            print(f"::error::could not open issue: {e2}")
        print(f"::error::missing label(s) {', '.join(args.labels)} — run: "
              f"gh label create <name> --repo $GITHUB_REPOSITORY")
        return 1


if __name__ == "__main__":
    sys.exit(main())
