#!/usr/bin/env bash
# verify.sh — gate CI on APS receipt validity.
#
# Looks for an audit bundle (``bundle.json`` by default) inside the
# given directory and verifies it offline with @veritasacta/verify.
#
# Exit codes:
#   0 — bundle signature(s) valid (proven authentic)
#   1 — at least one receipt failed signature check (proven tampered)
#   3 — usage error or malformed input

set -euo pipefail

RECEIPTS_DIR="${1:-receipts/}"
BUNDLE_NAME="${2:-bundle.json}"

if [[ ! -d "$RECEIPTS_DIR" ]]; then
  echo "verify.sh: '$RECEIPTS_DIR' is not a directory" >&2
  exit 3
fi

BUNDLE_PATH="$RECEIPTS_DIR/$BUNDLE_NAME"
if [[ ! -f "$BUNDLE_PATH" ]]; then
  echo "verify.sh: '$BUNDLE_PATH' not found" >&2
  exit 3
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "verify.sh: npx not found; install Node.js to use @veritasacta/verify" >&2
  exit 3
fi

# verify-artifact exit codes:
#   0 = signature valid
#   1 = signature invalid (proven tampered)
#   2 = verifier error (malformed input, missing key, parse failure)
set +e
npx --yes @veritasacta/verify "$BUNDLE_PATH" --bundle
rc=$?
set -e

case "$rc" in
  0) exit 0 ;;
  1) exit 1 ;;
  2) echo "verify.sh: verifier reported malformed input or parse failure" >&2; exit 3 ;;
  *) echo "verify.sh: unexpected verifier exit $rc" >&2; exit 1 ;;
esac
