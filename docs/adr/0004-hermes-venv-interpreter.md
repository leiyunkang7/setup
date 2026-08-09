# ADR 0004 — Run weekly-update.py under hermes's own venv interpreter

**Status**: accepted

The script `~/.hermes/scripts/weekly-update.py` imports `lark_oapi` in its non-dry-run send path, and `lark_oapi` is installed **only** inside hermes's own virtualenv at `/usr/local/lib/hermes-agent/venv/lib/python3.11/site-packages/lark_oapi/`. The system Python (`/usr/bin/python3`) cannot see it.

The `weekly-update-all` hermes cron therefore registers the script via a thin bash wrapper, `weekly-update.sh`, which `exec`s the venv interpreter explicitly:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec /usr/local/lib/hermes-agent/venv/bin/python "$(dirname "$0")/weekly-update.py" "$@"
```

The cron uses `--no-agent --script weekly-update.sh` so the wrapper IS the job. (Setting `--script weekly-update.py` directly would run it under `/usr/bin/env python3` and miss `lark_oapi`.)

Manual runs and `--dry-run` validation both work under any interpreter (system or hermes venv), because the dry-run path does not import `lark_oapi`. Only the real send path is interpreter-sensitive.

The wrapper at `~/.hermes/scripts/weekly-update.sh` is the canonical cron entry point. The repo copy at `/root/code/setup/scripts/weekly-update.sh` exists for version control and is byte-identical to the deployed wrapper; the deployed version invokes the script at `$(dirname "$0")/weekly-update.py`, so it resolves correctly whether the deployment is a real copy, a symlink, or in-repo.

If hermes is ever reinstalled to a different venv path, the wrapper must be updated. The orchestrator does not try to auto-detect.