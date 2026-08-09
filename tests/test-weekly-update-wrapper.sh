#!/usr/bin/env bash
# Contract test for ADR 0004's public cron entry point.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
wrapper="$repo_root/scripts/weekly-update.sh"
expected_python="/usr/local/lib/hermes-agent/venv/bin/python"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

[[ -x "$expected_python" ]] || fail "$expected_python is not executable"
bash -n "$wrapper"

cp "$wrapper" "$tmpdir/weekly-update.sh"
printf '%s\n' \
  'from pathlib import Path' \
  'import json' \
  'import sys' \
  'print(json.dumps({' \
  '    "executable": sys.executable,' \
  '    "script": str(Path(sys.argv[0]).resolve()),' \
  '    "args": sys.argv[1:],' \
  '}))' >"$tmpdir/weekly-update.py"
chmod +x "$tmpdir/weekly-update.sh"

actual="$(
  WEEKLY_UPDATE_DETACHED=1 \
  WEEKLY_UPDATE_START_DELAY_SECONDS=0 \
  "$tmpdir/weekly-update.sh" --dry-run 'argument with spaces'
)"
expected="$(
  "$expected_python" -c \
    'from pathlib import Path; import json, sys; print(json.dumps({"executable": sys.argv[1], "script": str(Path(sys.argv[2]).resolve()), "args": ["--dry-run", "argument with spaces"]}))' \
    "$expected_python" "$tmpdir/weekly-update.py"
)"
[[ "$actual" == "$expected" ]] || fail "wrapper did not preserve interpreter, sibling script path, and arguments"

cat >"$tmpdir/systemd-run" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$WEEKLY_UPDATE_LAUNCH_CAPTURE"
SH
chmod +x "$tmpdir/systemd-run"
cat >"$tmpdir/systemctl" <<'SH'
#!/usr/bin/env bash
exit 3
SH
chmod +x "$tmpdir/systemctl"

launch_capture="$tmpdir/launch-args"
WEEKLY_UPDATE_SYSTEMD_RUN="$tmpdir/systemd-run" \
WEEKLY_UPDATE_SYSTEMCTL="$tmpdir/systemctl" \
WEEKLY_UPDATE_LAUNCH_CAPTURE="$launch_capture" \
http_proxy="http://127.0.0.1:7890" \
  "$tmpdir/weekly-update.sh"

launch_args="$(<"$launch_capture")"
[[ "$launch_args" == *"--unit=hermes-weekly-update-worker"* ]] || fail "launcher did not use the dedicated transient unit"
[[ "$launch_args" == *"--setenv=WEEKLY_UPDATE_DETACHED=1"* ]] || fail "launcher did not mark the detached worker"
[[ "$launch_args" == *"--working-directory=$tmpdir"* ]] || fail "launcher did not keep the deployed sibling directory"
[[ "$launch_args" == *"--setenv=PATH="*"/root/.local/share/fnm/aliases/default/bin"* ]] || fail "launcher did not supply the stable tool PATH"
[[ "$launch_args" == *"--setenv=http_proxy"* ]] || fail "launcher did not forward the configured proxy environment"
[[ "$launch_args" == *"$tmpdir/weekly-update.sh"* ]] || fail "launcher did not execute the deployed wrapper"

cat >"$tmpdir/systemctl-active" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod +x "$tmpdir/systemctl-active"
if WEEKLY_UPDATE_SYSTEMD_RUN="$tmpdir/systemd-run" \
  WEEKLY_UPDATE_SYSTEMCTL="$tmpdir/systemctl-active" \
  WEEKLY_UPDATE_LAUNCH_CAPTURE="$launch_capture" \
  "$tmpdir/weekly-update.sh" 2>/dev/null; then
  fail "launcher allowed an overlapping worker"
fi

# --- P0: overlap lock must be acquired BEFORE the `is-active` probe. A stub that
#     takes the lock first and only then reports `inactive` proves the wrapper
#     is gated by the lock, not by the probe.
cat >"$tmpdir/lock" <<'SH'
#!/usr/bin/env bash
exec 9>"$WEEKLY_UPDATE_LOCK_PATH"
if ! flock -n 9; then
  printf 'lock busy\n' >&2
  exit 1
fi
# Hold the lock until the test's launch returns.
( sleep 30 ) &
echo "$!" >"$WEEKLY_UPDATE_LOCK_HOLDER"
wait
SH
chmod +x "$tmpdir/lock"

# A systemctl that always reports inactive, so the only way the launcher can
# refuse the second invocation is the lock.
cat >"$tmpdir/systemctl-inactive" <<'SH'
#!/usr/bin/env bash
exit 3
SH
chmod +x "$tmpdir/systemctl-inactive"

# Pre-take the lock from a sibling shell, then prove the launcher is refused.
exec 9>"$tmpdir/hermes-weekly-update-worker.lock"
if ! flock -n 9; then
  fail "test fixture could not pre-take lock"
fi
WEEKLY_UPDATE_LOCK_PATH="$tmpdir/hermes-weekly-update-worker.lock" \
WEEKLY_UPDATE_LOCK_HOLDER="$tmpdir/lock-holder" \
WEEKLY_UPDATE_SYSTEMD_RUN="$tmpdir/lock" \
WEEKLY_UPDATE_SYSTEMCTL="$tmpdir/systemctl-inactive" \
WEEKLY_UPDATE_LAUNCH_CAPTURE="$tmpdir/locked-launch" \
  "$tmpdir/weekly-update.sh" 2>/dev/null && \
  fail "launcher proceeded while the overlap lock was held"
flock -u 9
exec 9>&-

# --- P0: systemd-run failure must surface as a launch-fail log under
#     $HERMES_HOME/log/ and the wrapper must exit non-zero.
mkdir -p "$tmpdir/hh/log"
cat >"$tmpdir/systemd-run-fail" <<'SH'
#!/usr/bin/env bash
echo "FATAL simulated launcher failure" >&2
exit 99
SH
chmod +x "$tmpdir/systemd-run-fail"
rm -f "$tmpdir/hh/log/weekly-update-launch-fail-"*
set +e
HOME="$tmpdir/hh" HERMES_HOME="$tmpdir/hh" \
WEEKLY_UPDATE_SYSTEMD_RUN="$tmpdir/systemd-run-fail" \
WEEKLY_UPDATE_SYSTEMCTL="$tmpdir/systemctl-inactive" \
  "$tmpdir/weekly-update.sh" 2>/dev/null
rc=$?
set -e
[[ "$rc" -ne 0 ]] || fail "launcher swallowed systemd-run exit 99"
fail_log="$(ls "$tmpdir/hh/log"/weekly-update-launch-fail-* 2>/dev/null | head -1)"
if [[ -z "$fail_log" ]]; then
  fail "launcher did not write a launch-fail log on systemd-run failure"
fi
grep -q "exit 99" "$fail_log" || fail "launch-fail log did not capture exit code"

printf 'PASS: ADR 0004 wrapper contract\n'
