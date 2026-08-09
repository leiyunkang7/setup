# ADR 0004 — Run weekly-update.py under hermes's own venv interpreter

**Status**: accepted, implemented, and verified on this host

The script `~/.hermes/scripts/weekly-update.py` imports `lark_oapi` in its non-dry-run send path, and `lark_oapi` is installed **only** inside hermes's own virtualenv. The stable runtime contract is the venv entry point `/usr/local/lib/hermes-agent/venv/bin/python`; the Python minor version and its `site-packages` directory are implementation details that may change after a Hermes update. The system Python (`/usr/bin/python3`) cannot see `lark_oapi`. Real sends also require `python-dotenv` from the same venv (loaded only when present; the `_load_env_file` helper raises a `RuntimeError` on ImportError so the failure is loud rather than silent).

The `weekly-update-all` hermes cron therefore registers the script via a bash wrapper, `weekly-update.sh`. That wrapper has two phases:

1. The cron-facing phase launches `hermes-weekly-update-worker.service` as a transient systemd service and returns immediately. This moves the pipeline out of `hermes-gateway.service`'s cgroup before it invokes `hermes update`; Hermes intentionally drains and restarts every running gateway after an update, which would otherwise kill the cron process after its first upgrade step.
2. The detached worker phase waits briefly for the launching cron subprocess to exit, then `exec`s the venv interpreter explicitly:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec /usr/local/lib/hermes-agent/venv/bin/python "$(dirname "$0")/weekly-update.py" "$@"
```

The cron uses `--no-agent --script weekly-update.sh` so the wrapper IS the scheduled launcher. Hermes cron selects Bash for `.sh`/`.bash` files and its scheduler Python for every other extension; it deliberately does not honor a script's shebang. Registering `weekly-update.py` directly would both bypass the required venv selection and leave the pipeline inside the gateway cgroup.

The transient service receives an explicit, stable `PATH` containing the Hermes venv, the default FNM Node installation, Hermes-managed Node, Bun, Cargo, Atuin, and uv locations. It does not depend on the gateway process's startup environment or a per-shell `/run/user/.../fnm_multishells/...` path. Standard proxy variables are forwarded by name through `systemd-run`; if Hermes's sanitized cron environment lacks them, the launcher reads only proxy variables from this host's dedicated fish proxy config (mirrored in bash). Their values remain in the runtime environment rather than being embedded in this repository or the unit command line. The fixed unit name is also the overlap lock: the launcher rejects a new run while the worker service is active.

Manual runs and `--dry-run` validation both work under any interpreter (system or hermes venv), because the dry-run path does not import `lark_oapi`. Only the real send path is interpreter-sensitive.

The wrapper at `~/.hermes/scripts/weekly-update.sh` is the canonical cron entry point. The repo copy at `/root/code/setup/scripts/weekly-update.sh` exists for version control and is byte-identical to the deployed wrapper. The deployed wrapper and `weekly-update.py` are real sibling files under `~/.hermes/scripts/`; Hermes cron rejects its configured entry-point path if it resolves outside that directory.

The executable contract test is `tests/test-weekly-update-wrapper.sh`. It verifies Bash syntax, the transient-service launch contract, stable tool `PATH`, venv interpreter selection, sibling-script resolution, argument preservation, proxy forwarding, and overlap rejection. Separate runtime validation checks that the deployed and repo wrappers are byte-identical and that a real transient worker can complete `weekly-update.sh --dry-run` outside `hermes-gateway.service`, including while that gateway restarts.

Interpreter selection alone is not enough for a real cron send: Hermes sanitizes messaging credentials before spawning job scripts. `feishu.send()` therefore reloads `.env` from the active `HERMES_HOME` before validating the required Feishu configuration. `tests/test_feishu_cron_env.py` reproduces the scrubbed cron environment and verifies this behavior without contacting Feishu.

If Hermes is ever reinstalled to a different venv path, or this host stops using systemd, the wrapper must be updated. The orchestrator does not try to auto-detect those deployment changes.
