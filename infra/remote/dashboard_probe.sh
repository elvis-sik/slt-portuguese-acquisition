#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"
python3 - <<'PY'
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


root = Path.cwd()


def run(cmd: list[str], timeout: int = 5) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=timeout)
        return {"ok": proc.returncode == 0, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(), "returncode": proc.returncode}
    except Exception as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc), "returncode": 1}


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


jobs = []
jobs_root = root / "results" / "_jobs"
if jobs_root.exists():
    for job_dir in sorted([p for p in jobs_root.iterdir() if p.is_dir()], key=lambda p: p.name):
        pid = read(job_dir / "pid")
        alive = False
        if pid:
            alive = (Path("/proc") / pid).exists()
        jobs.append(
            {
                "id": job_dir.name,
                "status": read(job_dir / "status") or "unknown",
                "pid": pid,
                "alive": alive,
                "start_utc": read(job_dir / "start_utc"),
                "end_utc": read(job_dir / "end_utc"),
                "exit_code": read(job_dir / "exit_code"),
            }
        )

disk = shutil.disk_usage(root)
gpu = run(
    [
        "nvidia-smi",
        "--query-gpu=name,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
)

payload = {
    "repo_path": str(root),
    "git_commit": run(["git", "rev-parse", "--short", "HEAD"])["stdout"],
    "git_status": run(["git", "status", "--short", "--branch"])["stdout"],
    "uptime": read(Path("/proc/uptime")).split(" ")[0] if Path("/proc/uptime").exists() else "",
    "disk": {
        "total_bytes": disk.total,
        "used_bytes": disk.used,
        "free_bytes": disk.free,
    },
    "gpu": gpu,
    "jobs": jobs,
    "active_jobs": [job for job in jobs if job["status"] == "running" or job["alive"]],
    "last_update_utc": run(["date", "-u", "+%FT%TZ"])["stdout"],
}
print(json.dumps(payload, sort_keys=True))
PY
