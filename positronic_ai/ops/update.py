# =====================================================================
# Project Positronic — Polytemporal Cognitive Engram Memory Substrate
# Copyright (C) 2026 Shing Wong. All Rights Reserved.
# =====================================================================
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://gnu.org>.
# =====================================================================

"""Update verb — deferred self-update job + check/status/tail (port of update.ts).

Logs live at `$POSITRONIC_CACHE` (default `~/.cache/positronic`) as
`update-<jobId>.log` with a sibling `.lock` while running and a `<log>.exit`
file written by the detached job on completion.
"""
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"

def _base36(n: int) -> str:
    if n == 0:
        return "0"
    out = ""
    while n:
        out = _B36[n % 36] + out
        n //= 36
    return out

def _cache_dir() -> Path:
    base = os.environ.get("POSITRONIC_CACHE") or str(Path.home() / ".cache" / "positronic")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_log_path(job_id: str) -> str:
    return str(_cache_dir() / f"update-{job_id}.log")

def get_lock_path(job_id: str) -> str:
    return get_log_path(job_id) + ".lock"

def read_status(job_id: str) -> dict:
    """Return {jobId, status: "running"|"done", exitCode, logTail, logPath}."""
    log_path = get_log_path(job_id)
    p = Path(log_path)
    tail = p.read_text().split("\n")[-200:] if p.exists() else []
    lock = Path(get_lock_path(job_id)).exists()
    status = "running" if lock else ("done" if p.exists() else "running")
    return {"jobId": job_id, "status": status, "exitCode": None,
            "logTail": tail, "logPath": log_path}

def spawn_job(job_id: str, cmd: str) -> str:
    """Detach a bash job tee-ing output to the log; return the log path."""
    log_path = get_log_path(job_id)
    Path(get_lock_path(job_id)).write_text(str(os.getpid()))
    full = (f"{cmd} 2>&1 | tee {shlex.quote(log_path)}; "
            f"echo $? > {shlex.quote(log_path + '.exit')}")
    subprocess.Popen(["bash", "-c", full], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    return log_path

def run(*, check=False, pin=None, status=None, tail=None, dir=None) -> dict:
    d = dir or os.getcwd()
    if check:
        cmd = (
            f"git -C {shlex.quote(str(d))} ls-remote --heads origin 2>&1 | head; "
            f"echo '---'; "
            f"git -C {shlex.quote(str(d))} rev-list --count "
            f"HEAD..origin/beta 2>&1 | head -1")
        r = subprocess.run(["bash", "-c", cmd],
                           capture_output=True, text=True, check=False)
        m = re.search(r"\d+", r.stdout or "")
        behind = int(m.group(0)) if m else 0
        return {"behind": behind, "engramTagDiff": None,
                "npmOutdated": False, "logTail": []}
    if status:
        return read_status(status)
    if tail is not None:
        st = read_status("default")
        return {"logTail": st["logTail"][-(tail or 50):]}
    job_id = _base36(int(time.time() * 1000))
    spawn_job(job_id, f"cd {shlex.quote(str(d))} && git fetch && git diff --stat; "
                      f"npm ci && npm run build; npx vitest run")
    return {"jobId": job_id, "status": "running", "logPath": get_log_path(job_id)}