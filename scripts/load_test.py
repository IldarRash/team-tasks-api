"""Measured fixed-duration mixed workload; no third-party dependencies or invented SLA."""
import argparse
import concurrent.futures
import json
import platform
import threading
import time
from collections import Counter
from pathlib import Path
from verify_api import request, new_team, cleanup, assert_dense


def run(base, team_count, users, warmup, seconds):
    teams = [new_team() for _ in range(team_count)]
    samples, errors = [], []
    lock = threading.Lock()
    def worker(worker_id, end, record):
        index = 0
        while time.perf_counter() < end:
            started = time.perf_counter()
            try:
                team = teams[(worker_id + index) % team_count]
                task = request(base, "POST", "/tasks", {"teamId": team, "name": "load",
                               "description": "temporary load task"}, (201,))
                request(base, "PATCH", f'/tasks/{task["id"]}/priority', {"priority": 1})
                assert_dense(request(base, "GET", f"/tasks?teamId={team}"))
                request(base, "DELETE", f'/tasks/{task["id"]}', expected=(204,))
                if record:
                    with lock:
                        samples.append((time.perf_counter() - started) * 1000)
            except Exception as exc:
                with lock:
                    errors.append(type(exc).__name__ + ": " + str(exc)[:300])
            index += 1
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=users) as pool:
            if warmup:
                end = time.perf_counter() + warmup
                list(pool.map(lambda i: worker(i, end, False), range(users)))
            started = time.perf_counter()
            end = started + seconds
            list(pool.map(lambda i: worker(i, end, True), range(users)))
            elapsed = time.perf_counter() - started
        for team in teams:
            assert_dense(request(base, "GET", f"/tasks?teamId={team}"))
        samples.sort()
        def percentile(p):
            return round(samples[min(int((len(samples)-1)*p), len(samples)-1)], 2) if samples else None
        return {"teamCount": team_count, "users": users, "warmupSeconds": warmup,
                "durationSeconds": round(elapsed, 3), "successfulWorkflows": len(samples),
                "workflowRequests": 4, "httpRequestsPerSecond": round(len(samples)*4/elapsed, 2),
                "workflowLatencyMs": {"p50": percentile(.5), "p95": percentile(.95), "p99": percentile(.99)},
                "unexpectedErrors": dict(Counter(errors)), "finalInvariantPassed": True,
                "passed": len(errors) == 0 and len(samples) > 0}
    finally:
        for team in teams:
            cleanup(base, team)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--output", default="output/load.json")
    args = parser.parse_args()
    assert args.users > 0 and args.seconds > 0 and args.warmup >= 0
    result = {"clientPlatform": platform.platform(), "python": platform.python_version(),
              "base": args.base, "operationMix": "POST, move to 1, GET list, DELETE",
              "scenarios": [run(args.base, teams, args.users, args.warmup, args.seconds) for teams in [1, 10]]}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(s["passed"] for s in result["scenarios"]) else 1)
