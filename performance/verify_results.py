"""Offline, fail-closed verification for native-only performance evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from parse_gatling import parse as parse_gatling
from run_native import app_events, window
from stats_support import native_stats
from thread_trace import count_window, parse_traces
import run_native
import thread_trace


PROFILES = [(1, 20), (10, 20), (100, 20), (1000, 20), (1000, 100)]
MIB = 1024 ** 2


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fail(checks: list[str], message: str) -> None:
    checks.append(message)


def same(actual, expected) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9)


def digest(module) -> str:
    return hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()


def inspect_api(path: Path, checks: list[str]) -> dict:
    payload = load(path)
    record = payload[0] if isinstance(payload, list) and payload else payload
    host, config = record.get("HostConfig", {}), record.get("Config", {})
    nano_cpus = host.get("NanoCpus", 0)
    cpu_limit = nano_cpus == 2_000_000_000 or (host.get("CpuQuota") == 200000 and host.get("CpuPeriod") == 100000)
    memory_limit = host.get("Memory") == 1024 ** 3
    command = (config.get("Cmd") or [])
    user = str(config.get("User") or "")
    if not cpu_limit:
        fail(checks, f"{path}: API does not have a 2-CPU limit")
    if not memory_limit:
        fail(checks, f"{path}: API does not have a 1-GiB memory limit")
    if "-Xmx512m" not in command:
        fail(checks, f"{path}: API command lacks -Xmx512m")
    if not user or user in {"0", "root"}:
        fail(checks, f"{path}: API is not configured as non-root")
    if host.get("Privileged") is not False:
        fail(checks, f"{path}: API privileged mode is enabled or unspecified")
    if host.get("CapAdd"):
        fail(checks, f"{path}: API adds Linux capabilities")
    if host.get("SecurityOpt"):
        fail(checks, f"{path}: API overrides Docker security options")
    return {"cpuLimit": host.get("NanoCpus") or [host.get("CpuQuota"), host.get("CpuPeriod")], "memory": host.get("Memory"), "command": command, "user": user}


def sample_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def total(events: list[dict]) -> dict:
    if not events:
        return {"definite": 0, "ambiguous": 0, "exactCountAvailable": True}
    return count_window(events, min(event["entryEpochNs"] for event in events), min(event["entryEpochNs"] for event in events), max(event["returnEpochNs"] for event in events), max(event["returnEpochNs"] for event in events))


def verify_profile(directory: Path, expected: tuple[int, int], recorded: dict, checks: list[str]) -> dict:
    teams, users = expected
    summary = load(directory / "summary.json")
    container = inspect_api(directory / "container-inspect.json", checks)
    if summary.get("runtime") != "native" or (summary.get("teams"), summary.get("users")) != expected:
        fail(checks, f"{directory}: summary profile/runtime mismatch")
    trace = parse_traces(directory / "clone-traces")
    if not trace["validation"].get("exactCountAvailable"):
        fail(checks, f"{directory}: trace parser rejected evidence: {trace['validation']}")
    app_pid = load(directory / "app-pid.json").get("appPid")
    if not isinstance(app_pid, int) or app_pid <= 0:
        fail(checks, f"{directory}: invalid appPid")
        app_pid = -1
    events, members = app_events(trace["events"], app_pid)
    trace_tids = {int(match.group(1)) for path in (directory / "clone-traces").glob("threads.*") if (match := re.fullmatch(r"threads\.(\d+)", path.name))}
    member_tids = set(members)
    missing_group_files = member_tids - trace_tids
    if missing_group_files:
        fail(checks, f"{directory}: missing trace files for API thread-group TIDs {sorted(missing_group_files)}")
    non_thread_calls = sum(trace.get("nonThreadCounts", {}).values())
    if non_thread_calls == 0 and trace_tids != member_tids:
        fail(checks, f"{directory}: trace-file TIDs do not exactly match the API thread group without non-thread clones")
    warm_raw = parse_gatling(directory / "warmup" / "simulation.log")
    measured_raw = parse_gatling(directory / "measurement" / "simulation.log")
    for phase, raw in (("warmup", warm_raw), ("measurement", measured_raw)):
        if raw["failedRequests"] or raw["failedTransactions"]:
            fail(checks, f"{directory}: {phase} contains KO events")
        if raw["requests"] != raw["successfulTransactions"] * 4:
            fail(checks, f"{directory}: {phase} does not have four requests per lifecycle")
    calibrations = load(directory / "clock-calibrations.json")
    try:
        warm = window(events, warm_raw, calibrations["warmup"]["before"], calibrations["warmup"]["after"], False)
        measured = window(events, measured_raw, calibrations["measurement"]["before"], calibrations["measurement"]["after"], True)
    except Exception as error:
        fail(checks, f"{directory}: cannot replay phase windows: {error}")
        warm, measured = {}, {}
    all_events = total(events)
    if measured.get("ambiguous") != 0 or not measured.get("exactCountAvailable"):
        fail(checks, f"{directory}: measurement thread count is not exact")
    if all_events.get("ambiguous") != 0 or all_events.get("definite") != len(events):
        fail(checks, f"{directory}: total thread count is not exact")
    if summary.get("exactStartedOsThreads") != measured.get("definite"):
        fail(checks, f"{directory}: measurement count differs from summary")
    if warm.get("ambiguous") == 0:
        if summary.get("exactWarmupStartedOsThreads") != warm.get("definite"):
            fail(checks, f"{directory}: exact warmup count differs from summary")
    elif summary.get("exactWarmupStartedOsThreads") is not None:
        fail(checks, f"{directory}: ambiguous warmup must be null in summary")
    if summary.get("exactTotalStartedOsThreads") != len(events):
        fail(checks, f"{directory}: total count differs from accepted app events")

    invariant = summary.get("invariant", {})
    if invariant != {"dense": True, "teams": teams, "tasks": teams * 10, "seedTasksPreserved": True}:
        fail(checks, f"{directory}: dense 10-task/team invariant differs from expected")

    stats = native_stats(directory / "measurement" / "js" / "stats.js")
    lifecycle = next((value["stats"] for value in stats["contents"].values() if value.get("name") == "Task lifecycle"), None)
    if lifecycle is None:
        fail(checks, f"{directory}: Task lifecycle stats missing")
    else:
        stat_values = {
            "rps": stats["stats"]["meanNumberOfRequestsPerSecond"]["total"],
            "tps": lifecycle["meanNumberOfRequestsPerSecond"]["total"],
            "httpP95Ms": int(stats["stats"]["percentiles3"]["total"]),
            "transactionP95Ms": int(lifecycle["percentiles3"]["total"]),
        }
        for key, value in stat_values.items():
            if key.endswith("Ms"):
                if summary.get(key) != value:
                    fail(checks, f"{directory}: {key} differs from Gatling stats")
            elif not same(summary.get(key), value):
                fail(checks, f"{directory}: {key} differs from Gatling stats")
    baseline = load(directory / "baseline.json")
    all_rows = sample_rows(directory / "samples.jsonl")
    observed_tids = {
        tid
        for row in [baseline, *all_rows]
        for tid in row.get("osThreadIds", [])
    }
    untraced_observed_tids = observed_tids - member_tids
    if untraced_observed_tids:
        fail(checks, f"{directory}: baseline/sample OS thread IDs are absent from clone-trace API history: {sorted(untraced_observed_tids)}")
    rows = [row for row in all_rows if measured_raw["startEpochMs"] <= row["epochMs"] <= measured_raw["endEpochMs"]]
    if not rows:
        fail(checks, f"{directory}: no samples in raw measurement window")
    else:
        if not same(summary.get("rssMiB"), max(row["rssBytes"] for row in rows) / MIB):
            fail(checks, f"{directory}: RSS differs from in-window samples")
        if summary.get("osThreads") != max(row["osThreads"] for row in rows):
            fail(checks, f"{directory}: OS threads differ from in-window samples")
    if summary.get("errors") != 0:
        fail(checks, f"{directory}: summary errors are nonzero")
    if recorded != summary:
        fail(checks, f"{directory}: comparison native summary differs from summary.json")
    return {"profile": {"teams": teams, "users": users}, "container": container, "acceptedAppEvents": len(events), "threadGroupTids": members, "traceFiles": sorted(trace_tids), "counts": {"measurement": measured, "warmup": warm, "total": all_events}, "measurement": {"requests": measured_raw["requests"], "transactions": measured_raw["successfulTransactions"]}}


def optional_calibration(result_dir: Path, checks: list[str]) -> dict | None:
    candidates = [result_dir / "calibration", result_dir / "thread-calibration-native", result_dir.parent / "thread-calibration-native"]
    directory = next((path for path in candidates if path.exists()), None)
    if directory is None:
        return None
    parsed = parse_traces(directory)
    if not parsed["validation"].get("exactCountAvailable") or len(parsed["events"]) != 200:
        fail(checks, f"{directory}: native calibration must contain exactly 200 valid births")
    return {"directory": str(directory), "events": len(parsed["events"]), "validation": parsed["validation"]}


def verify(result_dir: Path) -> dict:
    checks: list[str] = []
    config, comparison = load(result_dir / "config.json"), load(result_dir / "comparison.json")
    methodology = config.get("methodology", {})
    expected_method = {"exactThreadTracing": True, "warmupSeconds": 30, "measurementSeconds": 60, "cpuLimit": 2, "memoryLimitMiB": 1024, "heapMaxMiB": 512}
    if methodology != expected_method:
        fail(checks, f"{result_dir}: methodology differs from native 30s/60s matrix")
    pairs = comparison.get("profiles", [])
    if len(pairs) != len(PROFILES):
        fail(checks, f"{result_dir}: expected five native profiles")
    runs = []
    for expected, pair in zip(PROFILES, pairs):
        teams, users = expected
        if (pair.get("teams"), pair.get("users")) != expected or not isinstance(pair.get("native"), dict):
            fail(checks, f"{result_dir}: invalid comparison profile {expected}")
            continue
        runs.append(verify_profile(result_dir / f"teams-{teams}-users-{users}" / "native", expected, pair["native"], checks))
    return {"resultDirectory": str(result_dir), "sourceHashes": {"threadTrace": digest(thread_trace), "runNative": digest(run_native)}, "runs": runs, "databaseVerification": "not asserted: this evidence retains API inspect only, not a DB inspect", "calibration": optional_calibration(result_dir, checks), "checks": checks, "passed": not checks}


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify native-only performance evidence without Docker")
    parser.add_argument("resultdir", type=Path, help="normally performance/results/native")
    args = parser.parse_args()
    result_dir = args.resultdir.resolve()
    result = verify(result_dir)
    (result_dir / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not result["passed"]:
        for message in result["checks"]:
            print(f"FAIL {message}")
        raise SystemExit(1)
    print(f"PASS {result_dir}")


if __name__ == "__main__":
    main()
