#!/usr/bin/env python3
"""Run a long, conservative refine/search loop for exam data sources.

Default duration is 10 hours. The loop does not mutate `questions.json`.
It records source reachability snapshots, rebuilds derived analysis, and leaves
an audit trail under `data/refine_runs.jsonl`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCES = DATA / "research_sources.json"
RUN_LOG = DATA / "refine_runs.jsonl"
SUMMARY = DATA / "refine_status.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_head(url: str, timeout: int = 20) -> dict:
    req = Request(url, headers={"User-Agent": "judicial-exam-refine/1.0"})
    started = time.time()
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read(120_000)
            return {
                "ok": True,
                "status": getattr(resp, "status", 200),
                "bytes_sampled": len(body),
                "sha256_sample": hashlib.sha256(body).hexdigest(),
                "elapsed_ms": int((time.time() - started) * 1000),
            }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:300],
            "elapsed_ms": int((time.time() - started) * 1000),
        }


def load_sources() -> list[dict]:
    with open(SOURCES, encoding="utf-8") as f:
        return json.load(f).get("sources", [])


def append_log(row: dict) -> None:
    DATA.mkdir(exist_ok=True)
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def rebuild_dataset() -> dict:
    cmd = [sys.executable, "scripts/build_questions.py"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180)
    return {
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def run_once(iteration: int, rebuild: bool, timeout_seconds: int) -> dict:
    sources = sorted(load_sources(), key=lambda s: (s.get("priority", 99), s.get("name", "")))
    checks = []
    for src in sources:
        result = fetch_head(src["url"], timeout=timeout_seconds)
        checks.append({**src, **result})
        time.sleep(1.5)

    row = {
        "ts": now_iso(),
        "iteration": iteration,
        "source_checks": checks,
        "rebuild": rebuild_dataset() if rebuild else None,
    }
    append_log(row)

    summary = {
        "last_run_at": row["ts"],
        "iteration": iteration,
        "ok_sources": sum(1 for c in checks if c.get("ok")),
        "failed_sources": [c["name"] for c in checks if not c.get("ok")],
        "next_action": "Review data/refine_runs.jsonl and promote verified changes into amendments/current_affairs data files.",
    }
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=10.0)
    parser.add_argument("--interval-minutes", type=float, default=30.0)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--no-rebuild", action="store_true")
    args = parser.parse_args()

    deadline = time.time() + args.hours * 3600
    interval = max(args.interval_minutes * 60, 60)
    iteration = 0
    while time.time() < deadline:
        iteration += 1
        summary = run_once(iteration, rebuild=not args.no_rebuild, timeout_seconds=args.timeout_seconds)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))


if __name__ == "__main__":
    main()
