#!/usr/bin/env bash
# Wrapper around weekly-update.py that forces hermes's own venv interpreter.
# hermes cron runs .py files with /usr/bin/env python3, which cannot see lark_oapi.
# This bash wrapper exists so we can register the script with --script under hermes cron
# while still using the venv interpreter (which has lark_oapi installed).
#
# At runtime, this wrapper lives at:
#   /root/.hermes/scripts/weekly-update.sh   (real, what cron invokes)
# and references the script living next to it:
#   /root/.hermes/scripts/weekly-update.py   (may be a symlink into this repo)
#
# A copy or symlink of this file should exist at:
#   <repo>/scripts/weekly-update.sh          (for version control)
#
# See ADR 0004 in docs/adr/.

set -euo pipefail

exec /usr/local/lib/hermes-agent/venv/bin/python "$(dirname "$0")/weekly-update.py" "$@"
