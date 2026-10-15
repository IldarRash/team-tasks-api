"""Native-only Gatling suite with exact Linux OS-thread births from strace."""

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from parse_gatling import parse
from stats_support import native_stats
from thread_trace import count_window, parse_traces


ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "-p", "team-tasks-native-performance", "-f", str(ROOT / "performance/compose.yaml")]
API = "team-tasks-native-performance-api-1"
DB = "team-tasks-native-performance-db-1"
BASE = "http://127.0.0.1:8084"
TEAM_BASE = 7_000_000_000_000
MIB = 1024 ** 2
CLOCK_MARGIN_NS = 1_000_000
HTTP_MARGIN_NS = 1_000_000


def command(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=kwargs.pop("check", True), capture_output=True, text=True, encoding="utf-8", **kwargs)


def dexec(*args):
    return command(["docker", "exec", API, *args]).stdout


def sql(statement):
    return command(["docker", "exec", "-i", DB, "psql", "-v", "ON_ERROR_STOP=1", "-U", "tasks", "-d", "taskdb", "-At"], input=statement).stdout


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as response:
        return json.load(response)


def wait_ready():
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            if get("/actuator/health")["status"] == "UP":
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("native API did not become healthy")


def seed(teams):
    end = TEAM_BASE + teams
    sql(f"""BEGIN; DELETE FROM tasks WHERE team_id >= {TEAM_BASE} AND team_id < {end}; DELETE FROM team_locks WHERE team_id >= {TEAM_BASE} AND team_id < {end}; INSERT INTO team_locks SELECT {TEAM_BASE}+i FROM generate_series(0,{teams-1}) AS i; INSERT INTO tasks SELECT gen_random_uuid(), {TEAM_BASE}+i, 'seed-'||p, 'Gatling fixture', p FROM generate_series(0,{teams-1}) AS i CROSS JOIN generate_series(1,10) AS p; COMMIT;""")


def invariant(teams):
    end = TEAM_BASE + teams
    bad = sql(f"""SELECT count(*) FROM (SELECT team_id FROM tasks WHERE team_id >= {TEAM_BASE} AND team_id < {end} GROUP BY team_id HAVING min(priority) <> 1 OR max(priority) <> count(*) OR count(DISTINCT priority) <> count(*)) AS bad;""").strip()
    count = sql(f"SELECT count(DISTINCT team_id), count(*) FROM tasks WHERE team_id >= {TEAM_BASE} AND team_id < {end};").strip()
    actual = tuple(map(int, count.split("|")))
    result = {"dense": bad == "0", "teams": actual[0], "tasks": actual[1], "seedTasksPreserved": actual == (teams, teams * 10)}
    if not result["dense"] or not result["seedTasksPreserved"]:
        raise AssertionError(result)
    return result


def tracee_pid():
    children = dexec("cat", "/proc/1/task/1/children").split()
    if len(children) != 1:
        raise RuntimeError(f"Expected one strace tracee child, got {children}")
    return int(children[0])


def generator():
    jcmd = Path(os.environ.get("JAVA_HOME", "")) / "bin" / ("jcmd.exe" if os.name == "nt" else "jcmd")
    if not jcmd.is_file():
        return None
    rows = command([str(jcmd), "-l"]).stdout.splitlines()
    pids = [int(row.split()[0]) for row in rows if "io.gatling.app.Gatling" in row]
    return {"pid": pids[0]} if len(pids) == 1 else None


def sample(pid):
    row = {"epochMs": int(time.time() * 1000), "appPid": pid, "generator": generator()}
    for line in dexec("cat", f"/proc/{pid}/status").splitlines():
        if line.startswith("VmRSS:"):
            row["rssBytes"] = int(line.split()[1]) * 1024
        if line.startswith("Threads:"):
            row["osThreads"] = int(line.split()[1])
    row["osThreadIds"] = [int(value) for value in dexec("ls", f"/proc/{pid}/task").split()]
    stats = command(["docker", "stats", "--no-stream", "--format", "{{json .}}", API, DB]).stdout
    row["containers"] = [json.loads(line) for line in stats.splitlines() if line.strip()]
    return row


class Collector:
    def __init__(self, path, pid):
        self.path = path
        self.pid = pid
        self.rows = []
        self.errors = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stop.is_set():
            began = time.monotonic()
            try:
                row = sample(self.pid)
                self.rows.append(row)
                with self.path.open("a", encoding="utf-8") as out:
                    out.write(json.dumps(row) + "\n")
            except Exception as error:
                self.errors.append(repr(error))
            self.stop.wait(max(.1, 5 - (time.monotonic() - began)))

    def finish(self):
        self.stop.set()
        self.thread.join(30)
        if self.thread.is_alive() or self.errors or not self.rows:
            raise RuntimeError(f"incomplete collector {self.errors}")


def calibration(label):
    process = subprocess.Popen(
        ["docker", "exec", "-i", API, "sh", "-c", "while IFS= read -r token; do date +%s.%N; done"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    samples = []
    try:
        for probe in range(30):
            before = time.time_ns()
            process.stdin.write(f"{probe}\n")
            process.stdin.flush()
            value = process.stdout.readline().strip()
            after = time.time_ns()
            seconds, nanos = value.split(".")
            samples.append({"hostBeforeNs": before, "dockerEpochNs": int(seconds) * 1_000_000_000 + int(nanos), "hostAfterNs": after})
    finally:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        process.wait(timeout=10)
    errors = process.stderr.read() if process.stderr else ""
    if process.returncode or len(samples) != 30:
        raise RuntimeError(f"clock calibration command failed: {errors}")
    low = max(row["dockerEpochNs"] - row["hostAfterNs"] - CLOCK_MARGIN_NS for row in samples)
    high = min(row["dockerEpochNs"] - row["hostBeforeNs"] + CLOCK_MARGIN_NS for row in samples)
    if low > high:
        raise RuntimeError(f"no clock offset intersection for {label}")
    return {"label": label, "samples": samples, "offsetLowerNs": low, "offsetUpperNs": high, "marginNs": CLOCK_MARGIN_NS}


def gatling(directory, teams, users, seconds, phase):
    before = set((ROOT / "build/reports/gatling").glob("*"))
    wrapper = str(ROOT / ("gradlew.bat" if os.name == "nt" else "gradlew"))
    args = [wrapper, "--console=plain", "gatlingRun", "--simulation", "com.ildarrash.teamtasks.performance.TaskLifecycleSimulation", f"-DbaseUrl={BASE}", f"-Dteams={teams}", f"-Dusers={users}", f"-DdurationSeconds={seconds}", f"-DteamBaseId={TEAM_BASE}"]
    with (directory / f"{phase}-console.log").open("w", encoding="utf-8") as out:
        result = subprocess.run(args, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, timeout=seconds + 240)
    made = set((ROOT / "build/reports/gatling").glob("*")) - before
    if len(made) != 1 or result.returncode:
        raise RuntimeError(f"Gatling {phase} failed: {made}")
    shutil.copytree(next(iter(made)), directory / phase)
    return parse(directory / phase / "simulation.log")


def window(events, gatling_events, before, after, strict):
    low = max(before["offsetLowerNs"], after["offsetLowerNs"])
    high = min(before["offsetUpperNs"], after["offsetUpperNs"])
    if low > high:
        raise RuntimeError("clock drift left no phase offset intersection")
    start = int(gatling_events["startEpochMs"]) * 1_000_000
    end = int(gatling_events["endEpochMs"]) * 1_000_000
    found = count_window(events, start + low - HTTP_MARGIN_NS, start + high + HTTP_MARGIN_NS, end + low - HTTP_MARGIN_NS, end + high + HTTP_MARGIN_NS)
    found.update({"offsetLowerNs": low, "offsetUpperNs": high, "httpMarginNs": HTTP_MARGIN_NS})
    if strict and (not found.get("exactCountAvailable") or found["ambiguous"]):
        raise RuntimeError(f"non-exact measurement thread count {found}")
    return found


def app_events(all_events, pid):
    members = {pid}
    kept = []
    for event in sorted(all_events, key=lambda row: (row["entryEpochNs"], row["returnEpochNs"])):
        if event["parentTid"] in members:
            kept.append(event)
            members.add(event["childTid"])
    return kept, sorted(members)


def run(directory, teams, users, warmup, duration):
    directory.mkdir(parents=True)
    print(f"START native teams={teams} users={users}", flush=True)
    command(COMPOSE + ["up", "-d", "--force-recreate", "api"])
    wait_ready()
    pid = tracee_pid()
    (directory / "startup.log").write_text(command(["docker", "logs", API]).stdout, encoding="utf-8")
    (directory / "container-inspect.json").write_text(command(["docker", "inspect", API]).stdout, encoding="utf-8")
    (directory / "app-pid.json").write_text(json.dumps({"stracePid": 1, "appPid": pid}, indent=2) + "\n")
    version = command(["docker", "exec", API, "strace", "-V"])
    (directory / "strace-version.txt").write_text(version.stdout + version.stderr)
    sql(f"DELETE FROM tasks WHERE team_id >= {TEAM_BASE} AND team_id < {TEAM_BASE + 1000}; DELETE FROM team_locks WHERE team_id >= {TEAM_BASE} AND team_id < {TEAM_BASE + 1000};")
    seed(teams)
    sql("VACUUM (ANALYZE) tasks; VACUUM (ANALYZE) team_locks;")
    warmup_before = calibration("warmup-before")
    warmup_events = gatling(directory, teams, users, warmup, "warmup")
    warmup_after = calibration("warmup-after")
    invariant(teams)
    (directory / "baseline.json").write_text(json.dumps(sample(pid), indent=2) + "\n")
    collector = Collector(directory / "samples.jsonl", pid)
    collector.thread.start()
    try:
        measurement_before = calibration("measurement-before")
        measured_events = gatling(directory, teams, users, duration, "measurement")
        measurement_after = calibration("measurement-after")
    finally:
        collector.finish()
    proof = invariant(teams)
    command(["docker", "exec", API, "sync"])
    command(["docker", "cp", f"{API}:/thread-trace", str(directory)])
    (directory / "thread-trace").rename(directory / "clone-traces")
    trace = parse_traces(directory / "clone-traces")
    (directory / "thread-trace-parse.json").write_text(json.dumps(trace, indent=2) + "\n")
    if not trace["validation"].get("exactCountAvailable"):
        raise RuntimeError(trace["validation"])
    events, members = app_events(trace["events"], pid)
    (directory / "clock-calibrations.json").write_text(json.dumps({"warmup": {"before": warmup_before, "after": warmup_after}, "measurement": {"before": measurement_before, "after": measurement_after}}, indent=2) + "\n")
    warmup_count = window(events, warmup_events, warmup_before, warmup_after, False)
    measurement_count = window(events, measured_events, measurement_before, measurement_after, True)
    entries = [event["entryEpochNs"] for event in events]
    returns = [event["returnEpochNs"] for event in events]
    total = count_window(events, min(entries, default=0), min(entries, default=0), max(returns, default=0), max(returns, default=0))
    stats = native_stats(directory / "measurement/js/stats.js")
    lifecycle = next(row["stats"] for row in stats["contents"].values() if row["name"] == "Task lifecycle")
    rows = [row for row in collector.rows if measured_events["startEpochMs"] <= row["epochMs"] <= measured_events["endEpochMs"]]
    if not rows:
        raise RuntimeError("no in-window RSS sample")
    summary = {"runtime": "native", "teams": teams, "users": users, "warmupSeconds": warmup, "measurementSeconds": duration, "rps": float(stats["stats"]["meanNumberOfRequestsPerSecond"]["total"]), "tps": float(lifecycle["meanNumberOfRequestsPerSecond"]["total"]), "httpP95Ms": int(stats["stats"]["percentiles3"]["total"]), "transactionP95Ms": int(lifecycle["percentiles3"]["total"]), "rssMiB": max(row["rssBytes"] for row in rows) / MIB, "osThreads": max(row["osThreads"] for row in rows), "errors": measured_events["failedRequests"], "invariant": proof, "exactStartedOsThreads": measurement_count["definite"], "exactWarmupStartedOsThreads": warmup_count["definite"] if not warmup_count["ambiguous"] else None, "exactTotalStartedOsThreads": total["definite"], "threadCountMethod": "successful CLONE_THREAD clone/clone3 calls in initial API thread group; conservative Docker/Gatling epoch bounds", "threadCountValidation": {"measurement": measurement_count, "warmup": warmup_count, "total": total, "trace": trace["validation"], "threadGroupTids": members}}
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--warmup", type=int)
    parser.add_argument("--duration", type=int)
    parser.add_argument("--smoke2users", action="store_true")
    args = parser.parse_args()
    warmup = args.warmup if args.warmup is not None else (2 if args.smoke2users else 30)
    duration = args.duration if args.duration is not None else (10 if args.smoke2users else 60)
    if warmup <= 0 or duration <= 0:
        parser.error("--warmup and --duration must be positive seconds")
    profiles = [(1, 2)] if args.smoke2users else [(1, 20), (10, 20), (100, 20), (1000, 20), (1000, 100)]
    if args.output:
        output = (ROOT / args.output).resolve()
    else:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = ROOT / "performance/results" / f"native-{stamp}"
    if not output.is_relative_to(ROOT / "performance") or (output.exists() and any(output.iterdir())):
        raise ValueError("--output must be a new directory below performance/")
    output.mkdir(parents=True, exist_ok=True)
    payload = {"methodology": {"exactThreadTracing": True, "warmupSeconds": warmup, "measurementSeconds": duration, "cpuLimit": 2, "memoryLimitMiB": 1024, "heapMaxMiB": 512}, "profiles": []}
    (output / "config.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"OUTPUT {output}", flush=True)
    command(COMPOSE + ["up", "-d", "db"])
    command(COMPOSE + ["build", "api"])
    for teams, users in profiles:
        summary = run(output / f"teams-{teams}-users-{users}" / "native", teams, users, warmup, duration)
        payload["profiles"].append({"teams": teams, "users": users, "native": summary})
        (output / "comparison.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"COMPLETE {output}", flush=True)


if __name__ == "__main__":
    main()
