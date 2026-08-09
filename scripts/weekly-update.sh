#!/usr/bin/env bash
# Wrapper around weekly-update.py that forces Hermes's own venv interpreter and
# detaches the destructive upgrade pipeline from the gateway's systemd cgroup.
#
# Hermes cron runs this file inside hermes-gateway.service. `hermes update`
# intentionally restarts every gateway, so running the pipeline in that cgroup
# would kill the cron script after its first step. The outer invocation starts a
# transient system service and exits; the detached worker survives that restart.
#
# At runtime, this wrapper and weekly-update.py are real sibling files under
# ~/.hermes/scripts/. See ADR 0004 in docs/adr/.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hermes_python="/usr/local/lib/hermes-agent/venv/bin/python"

if [[ "${WEEKLY_UPDATE_DETACHED:-}" != "1" ]]; then
  systemd_run="${WEEKLY_UPDATE_SYSTEMD_RUN:-/usr/bin/systemd-run}"
  systemd_args=(
    --unit=hermes-weekly-update-worker
    --collect
    --quiet
    --working-directory="$script_dir"
    --setenv=HOME=/root
    --setenv=HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
    --setenv=PATH="/usr/local/lib/hermes-agent/venv/bin:/root/.local/share/fnm/aliases/default/bin:/root/.hermes/node/bin:/root/.local/bin:/root/.bun/bin:/root/.cargo/bin:/root/.atuin/bin:/root/.hermes/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    --setenv=WEEKLY_UPDATE_DETACHED=1
    --setenv=WEEKLY_UPDATE_START_DELAY_SECONDS="${WEEKLY_UPDATE_START_DELAY_SECONDS:-8}"
  )
  # The gateway's sanitized script environment may not contain shell proxy
  # variables. Load the host's dedicated fish proxy config when no proxy was
  # inherited; systemd's manager starts transient services with a clean env.
  if [[ -z "${http_proxy:-}" && -z "${HTTP_PROXY:-}" ]] && [[ -r /root/.config/fish/proxy.fish ]]; then
    while IFS= read -r -d '' proxy_assignment; do
      case "$proxy_assignment" in
        http_proxy=*|https_proxy=*|all_proxy=*|no_proxy=*|HTTP_PROXY=*|HTTPS_PROXY=*|ALL_PROXY=*|NO_PROXY=*)
          export "$proxy_assignment"
          ;;
      esac
    done < <(
      env -i HOME=/root /usr/bin/fish -c \
        'source /root/.config/fish/proxy.fish; env -0'
    )
  fi
  # --- Overlap lock. The `is-active` probe below is a fast-path convenience,
  #     but it is a classic TOCTOU window: two near-simultaneous crons can both
  #     see `inactive` and both call `systemd-run`. The exclusive flock makes
  #     the second caller wait / fail immediately. The lock is released when
  #     the launcher exits, which is well before the worker is scheduled to
  #     start (8s default), so the worker still runs lock-free.
  lock_path="${WEEKLY_UPDATE_LOCK_PATH:-/var/lock/hermes-weekly-update-worker.lock}"
  if command -v flock >/dev/null 2>&1; then
    exec 9>"$lock_path"
    if ! flock -n 9; then
      printf 'weekly-update worker is already launching; refusing overlap\n' >&2
      exit 1
    fi
  fi
  systemctl_bin="${WEEKLY_UPDATE_SYSTEMCTL:-/usr/bin/systemctl}"
  if "$systemctl_bin" is-active --quiet hermes-weekly-update-worker.service; then
    printf 'weekly-update worker is already running; refusing overlap\n' >&2
    exit 1
  fi
  for proxy_var in http_proxy https_proxy all_proxy no_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY; do
    if [[ -n "${!proxy_var:-}" ]]; then
      # NAME without =VALUE tells systemd-run to copy the caller's value without
      # exposing it in this script or the unit's command line.
      systemd_args+=("--setenv=$proxy_var")
    fi
  done
  set +e
  "$systemd_run" "${systemd_args[@]}" "$script_dir/weekly-update.sh" "$@"
  worker_rc=$?
  set -e
  if [[ "$worker_rc" -ne 0 ]]; then
    # systemd-run failed (D-Bus down, polkit denied, transient registration
    # rejected). Without a launch-fail log the operator only sees cron
    # delivery's opaque rc; surface enough context to act.
    log_dir="${HERMES_HOME:-/root/.hermes}/log"
    mkdir -p "$log_dir" || true
    fail_log="$log_dir/weekly-update-launch-fail-$(date -u +%Y%m%dT%H%M%SZ).log"
    {
      printf 'systemd-run exit %s\n' "$worker_rc"
      printf 'command: %s %s\n' "$systemd_run" "${systemd_args[*]}"
      printf 'wrapper: %s\n' "$script_dir/weekly-update.sh"
      printf 'args: %s\n' "$*"
    } >"$fail_log" 2>/dev/null || true
    printf 'weekly-update launch failed (systemd-run exit %s); see %s\n' "$worker_rc" "$fail_log" >&2
  fi
  exit "$worker_rc"
fi

start_delay="${WEEKLY_UPDATE_START_DELAY_SECONDS:-8}"
if [[ "$start_delay" != "0" ]]; then
  sleep "$start_delay"
fi

exec "$hermes_python" "$script_dir/weekly-update.py" "$@"
