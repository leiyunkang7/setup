#!/usr/bin/env python3
"""Contract test for ADR 0006's destructive boundary.

ADR 0006 line 19 asserts that the worker survives a `systemctl restart
hermes-gateway.service` while the launcher's transient worker is running,
because the worker lives in its own cgroup and `hermes update` drains the
gateway cgroup. The earlier manual probe (2026-08-09 16:34 UTC) confirmed this
on this host, but until now the contract had no executable regression test.

This test launches the real wrapper (`/root/.hermes/scripts/weekly-update.sh`),
captures the transient unit's PID and cgroup, then restarts the gateway and
asserts the worker PID + cgroup are unchanged. It does NOT call `hermes update`
or any package manager — the boundary test is purely about cgroup survival
under a gateway restart.

Skipped when:
  * not running as root (systemd-run requires it),
  * no systemd manager (sandbox / container without init),
  * the real deployed wrapper is missing (the test would have to use a stub,
    which no longer proves anything).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

GATEWAY = "hermes-gateway.service"
WORKER = "hermes-weekly-update-worker.service"
WRAPPER = Path("/root/.hermes/scripts/weekly-update.sh")
EXPECTED_CGROUP = f"/system.slice/{WORKER}"


def _hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".hermes"


def _systemd_manager_available() -> bool:
    if not shutil.which("systemctl"):
        return False
    try:
        proc = subprocess.run(
            ["systemctl", "is-system-running"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    # running | degraded | maintenance count as "manager alive" for our purposes.
    return proc.stdout.strip() in {"running", "degraded", "maintenance"}


class GatewayRestartSurvivalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.geteuid() != 0:
            raise unittest.SkipTest("requires root (systemd-run)")
        if not _systemd_manager_available():
            raise unittest.SkipTest("no live systemd manager in this env")
        if not WRAPPER.is_file():
            raise unittest.SkipTest(f"deployed wrapper not present: {WRAPPER}")

    def _prop(self, service: str, prop: str) -> str:
        proc = subprocess.run(
            ["systemctl", "show", service, f"--property={prop}", "--value"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.stdout.strip()

    def test_worker_survives_hermes_gateway_restart(self) -> None:
        before_gateway_pid = self._prop(GATEWAY, "MainPID")
        self.assertNotEqual(before_gateway_pid, "0", "gateway not running; restart test meaningless")
        self.assertNotEqual(before_gateway_pid, "", "could not read gateway MainPID")

        # Real launcher: 12s start delay keeps the worker busy long enough for
        # us to observe its PID, then trigger a gateway restart before the
        # worker actually runs `hermes update`.
        env = {**os.environ, "WEEKLY_UPDATE_START_DELAY_SECONDS": "12"}
        proc = subprocess.run(
            [str(WRAPPER), "--dry-run"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        # The launcher returns immediately after systemd-run. rc=0 means a
        # worker was registered.
        if proc.returncode != 0:
            self.fail(
                f"launcher returned {proc.returncode}: stdout={proc.stdout!r} "
                f"stderr={proc.stderr!r}"
            )

        # Wait for the transient unit to come up. `MainPID` becomes non-zero
        # only after the detached worker execs python.
        deadline = time.monotonic() + 20.0
        worker_pid = ""
        worker_cgroup = ""
        while time.monotonic() < deadline:
            worker_pid = self._prop(WORKER, "MainPID")
            worker_cgroup = self._prop(WORKER, "ControlGroup")
            if worker_pid and worker_pid != "0" and worker_cgroup:
                break
            time.sleep(0.1)
        self.assertTrue(worker_pid and worker_pid != "0", "transient worker did not come up in time")
        self.assertEqual(EXPECTED_CGROUP, worker_cgroup, "worker not in expected cgroup")

        # Restart the gateway — this is the operation ADR 0006 promises the
        # worker survives.
        subprocess.run(
            ["systemctl", "restart", GATEWAY],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        deadline = time.monotonic() + 30.0
        after_gateway_pid = ""
        gateway_state = ""
        while time.monotonic() < deadline:
            after_gateway_pid = self._prop(GATEWAY, "MainPID")
            gateway_state = self._prop(GATEWAY, "ActiveState")
            if (
                gateway_state == "active"
                and after_gateway_pid
                and after_gateway_pid != "0"
                and after_gateway_pid != before_gateway_pid
            ):
                break
            time.sleep(0.1)
        self.assertEqual("active", gateway_state, "gateway failed to come back active")
        self.assertNotEqual(
            before_gateway_pid,
            after_gateway_pid,
            "gateway MainPID did not change; restart was a no-op (loopback, not isolation)",
        )

        after_worker_pid = self._prop(WORKER, "MainPID")
        after_worker_cgroup = self._prop(WORKER, "ControlGroup")
        self.assertEqual(
            worker_pid,
            after_worker_pid,
            "transient worker PID changed across gateway restart — cgroup isolation broken",
        )
        self.assertEqual(
            worker_cgroup,
            after_worker_cgroup,
            "transient worker cgroup drifted during gateway restart",
        )

        # Wait for the worker to finish naturally. Its exit must be clean.
        deadline = time.monotonic() + 240.0
        final_state = ""
        while time.monotonic() < deadline:
            final_state = self._prop(WORKER, "ActiveState")
            if final_state not in {"active", "activating"}:
                break
            time.sleep(1.0)
        result = self._prop(WORKER, "Result")
        exec_status = self._prop(WORKER, "ExecMainStatus")
        self.assertEqual(
            "success",
            result,
            f"worker final Result={result!r} (state={final_state!r})",
        )
        self.assertEqual("0", exec_status, f"worker ExecMainStatus={exec_status!r}")

        # And the dry-run produced a complete artifact set.
        cache = _hermes_home() / "cache" / "weekly-update"
        runs = sorted(p for p in cache.iterdir() if p.is_dir())
        self.assertTrue(runs, "no run dir produced under cache/weekly-update/")
        last = runs[-1]
        for name in ("pre.json", "post.json", "digest.md", "feishu-payload.json"):
            self.assertTrue((last / name).is_file(), f"missing artifact: {name}")


if __name__ == "__main__":
    unittest.main()
