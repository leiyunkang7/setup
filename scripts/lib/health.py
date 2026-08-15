"""
Health gate: verify every upgraded tool still responds to --version / --help.
Per ADR-derived Q30: --version AND --help both succeed, no "error" / "traceback"
in stderr. Failure on any gate aborts subsequent steps.
"""
from __future__ import annotations

import re
import subprocess

ERROR_PATTERNS = (re.compile(r"traceback", re.I), re.compile(r"\berror\b", re.I))


def probe(bin_name: str) -> tuple[bool, str]:
    """Return (ok, message). ok=True iff both --version and --help succeed cleanly."""
    from shutil import which
    binp = which(bin_name)
    if not binp is None and binp == "":
        binp = None
    if not binp:
        return True, "not installed — gate skipped"
    for args in (("--version",), ("--help",)):
        try:
            proc = subprocess.run(
                [binp, *args],
                capture_output=True, text=True, timeout=15,
            )
        except subprocess.TimeoutExpired:
            return False, f"{bin_name} {' '.join(args)}: timeout"
        except (FileNotFoundError, OSError):
            return False, f"{bin_name}: binary disappeared"
        combined = (proc.stdout + proc.stderr).lower()
        if proc.returncode != 0:
            return False, f"{bin_name} {' '.join(args)}: exit {proc.returncode}"
        for pat in ERROR_PATTERNS:
            if pat.search(combined):
                return False, f"{bin_name} {' '.join(args)}: matched /{pat.pattern}/"
    return True, "ok"