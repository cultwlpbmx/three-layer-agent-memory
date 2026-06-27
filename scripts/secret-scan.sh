#!/usr/bin/env bash
#
# secret-scan.sh — catch secrets before they hit a public memory library.
#
# The paradigm stores memory as plain Markdown that often gets pushed to a
# public git remote. The surface-layer rule is "write WHERE the key is, never
# the key itself" (see SCHEMA.md). This script is the safety net for when
# someone forgets — run it before every push.
#
# Exit 0 = clean, 1 = potential secret found (review the hits).
#
# Usage:
#   ./scripts/secret-scan.sh            # scan the whole repo
#   ./scripts/secret-scan.sh path/...   # scan specific paths

set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

# Patterns covering the common leaks. False positives on placeholders like
# <KEY> or "where: /etc/.env" are unlikely — these need real-looking material.
PATTERNS='ghp_[0-9A-Za-z]{36}|gho_[0-9A-Za-z]{36}|ghs_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{82}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|xox[baprs]-[0-9A-Za-z-]{12,}|LTAI[0-9A-Za-z]{12,}|-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----|([a-z][a-z0-9+.\-]*://[^:/\s]+:[^@\s]+@[^\s]+)'

# Files that legitimately contain these patterns (this scanner + the workflow).
EXCLUDES=(':(exclude)scripts/secret-scan.sh' ':(exclude).github/workflows/secret-scan.yml')

if [ "$#" -gt 0 ]; then
  TARGETS=("$@")
else
  TARGETS=(".")
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  hits=$(git grep -nE -I -- "$PATTERNS" "${TARGETS[@]}" "${EXCLUDES[@]}" 2>/dev/null || true)
else
  excludes_grep=()
  for e in scripts/secret-scan.sh .github/workflows/secret-scan.yml; do
    excludes_grep+=("--exclude=$(basename "$e")")
  done
  hits=$(grep -rnE --exclude-dir=.git "${excludes_grep[@]}" "$PATTERNS" "${TARGETS[@]}" 2>/dev/null || true)
fi

if [ -n "$hits" ]; then
  printf '❌ Potential secrets found — review before pushing:\n\n%s\n\n' "$hits" >&2
  printf 'If these are placeholders/examples, narrow the pattern or add the file to EXCLUDES.\n' >&2
  exit 1
fi

printf '✅ No obvious secrets found.\n'
exit 0