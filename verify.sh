#!/usr/bin/env bash
# verify.sh — gate CI on APS receipt validity.
#
# Exit codes:
#   0 — every receipt signature verifies and the chain is intact
#   1 — at least one signature failed
#   2 — chain has a gap (a receipt references an unknown parent)
#   3 — usage error or missing verifier

set -euo pipefail

RECEIPTS_DIR="${1:-receipts/}"

if [[ ! -d "$RECEIPTS_DIR" ]]; then
  echo "verify.sh: '$RECEIPTS_DIR' is not a directory" >&2
  exit 3
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "verify.sh: npx not found; install Node.js to use @veritasacta/verify" >&2
  exit 3
fi

# @veritasacta/verify prints one JSON object per receipt to stdout and
# uses exit 0 for all-pass, 10 for signature failure, 20 for chain gap.
# Translate to the exit codes this script promises.
set +e
npx --yes @veritasacta/verify "$RECEIPTS_DIR"
rc=$?
set -e

case "$rc" in
  0)  exit 0 ;;
  10) exit 1 ;;
  20) exit 2 ;;
  *)  echo "verify.sh: unexpected verifier exit $rc" >&2; exit "$rc" ;;
esac
