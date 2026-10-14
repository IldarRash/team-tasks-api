"""Run Gatling and capture real JVM/container evidence. Python orchestrates; Gatling generates load."""
import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from parse_gatling import parse

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "-p", "team-tasks-benchmark", "-f", str(ROOT / "performance/compose.yaml")]
API = "team-tasks-benchmark-api-1"
DB = "team-tasks-benchmark-db-1"
BASE = "http://127.0.0.1:8081"
TEAM_BASE = 7_000_000_000_000


def generator_process():
    executable = Path(os.environ.get("JAVA_HOME", "")) / "bin" / ("jcmd.exe" if os.name == "nt" else "jcmd")
    if not executable.is_file():
        return None
    listing = command([str(executable), "-l"]).stdout
    pids = [int(line.split()[0]) for line in listing.splitlines() if "io.gatling.app.Gatling" in line]
    if len(pids) != 1:
        return None
    pid = pids[0]
    if os.name == "nt":
        code = f"$p=Get-Process -Id {pid}; @{{pid=$p.Id;rssBytes=$p.WorkingSet64;osThreads=$p.Threads.Count;cpuSeconds=$p.CPU}} | ConvertTo-Json -Compress"
        response = command(["powershell.exe", "-NoProfile", "-Command", code], check=False)
        return json.loads(response.stdout) if response.returncode == 0 else None
    status = Path(f"/proc/{pid}/status")
    if status.is_file():
        text = status.read_text()
        return {"pid": pid, "rssBytes": int(re.search(r"VmRSS:\s+(\d+)", text).group(1))*1024,
                "osThreads": int(re.search(r"Threads:\s+(\d+)", text).group(1))}
    return None


def command(args, *, check=True, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=check, capture_output=True, text=True, encoding="utf-8", **kwargs)


def docker_exec(container, *args, check=True):
    return command(["docker", "exec", container, *args], check=check).stdout


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as response:
        return json.load(response)


def wait_ready():
    deadline = time.monotonic() + 120
    while True:
        try:
            if get("/actuator/health")["status"] == "UP":
                return
        except Exception:
            if time.monotonic() > deadline:
                raise
        time.sleep(1)


def sql(statement):
    return command(["docker", "exec", "-i", DB, "psql", "-v", "ON_ERROR_STOP=1", "-U", "tasks", "-d", "taskdb", "-At"], input=statement).stdout


def seed(teams):
    # Dedicated benchmark database and fixture range; application database is never addressed.
    end = TEAM_BASE + teams
    sql(f"""BEGIN;
    DELETE FROM tasks WHERE team_id >= {TEAM_BASE} AND team_id < {end};
    DELETE FROM team_locks WHERE team_id >= {TEAM_BASE} AND team_id < {end};
    INSERT INTO team_locks SELECT {TEAM_BASE}+i FROM generate_series(0,{teams-1}) AS i;
    INSERT INTO tasks SELECT gen_random_uuid(), {TEAM_BASE}+i, 'seed-'||p,
      'Gatling fixture', p FROM generate_series(0,{teams-1}) AS i CROSS JOIN generate_series(1,10) AS p;
    COMMIT;""")


def invariant(teams):
    end = TEAM_BASE + teams
    bad = sql(f"""SELECT count(*) FROM (SELECT team_id FROM tasks
        WHERE team_id >= {TEAM_BASE} AND team_id < {end} GROUP BY team_id
        HAVING min(priority) <> 1 OR max(priority) <> count(*) OR count(DISTINCT priority) <> count(*)) AS bad;""").strip()
    counts = sql(f"SELECT count(DISTINCT team_id),count(*) FROM tasks WHERE team_id >= {TEAM_BASE} AND team_id < {end};").strip()
    team_count, task_count = map(int, counts.split("|"))
    result = {"dense": bad == "0", "teams": team_count, "tasks": task_count,
              "seedTasksPreserved": team_count == teams and task_count == teams * 10}
    if not result["dense"] or not result["seedTasksPreserved"]:
        raise AssertionError(result)
    return result


def metric(name, tag=None):
    suffix = "?tag=" + tag if tag else ""
    data = get("/actuator/metrics/" + name + suffix)
    return {m["statistic"]: m["value"] for m in data["measurements"]}


def sample():
    result = {"epochMs": int(time.time() * 1000)}
    for name, key, tag in [
        ("jvm.threads.live", "jvmLiveThreads", None),
        ("jvm.threads.peak", "jvmPeakThreads", None),
        ("jvm.threads.started", "jvmStartedThreads", None),
        ("jvm.threads.daemon", "jvmDaemonThreads", None),
        ("jvm.memory.used", "heapUsedBytes", "area:heap"),
        ("jvm.memory.committed", "heapCommittedBytes", "area:heap"),
        ("jvm.memory.max", "heapMaxBytes", "area:heap"),
        ("hikaricp.connections.active", "dbActiveConnections", None),
    ]:
        values = metric(name, tag)
        result[key] = next(iter(values.values()))
    gc = metric("jvm.gc.pause")
    result["gcCount"] = gc.get("COUNT", 0)
    result["gcTotalSeconds"] = gc.get("TOTAL_TIME", 0)
    for line in docker_exec(API, "cat", "/proc/1/status").splitlines():
        if line.startswith("VmRSS:"):
            result["processRssBytes"] = int(line.split()[1]) * 1024
        if line.startswith("Threads:"):
            result["osThreads"] = int(line.split()[1])
    stats = command(["docker", "stats", "--no-stream", "--format", "{{json .}}", API, DB]).stdout
    result["docker"] = [json.loads(line) for line in stats.splitlines() if line.strip()]
    result["generator"] = generator_process()
    return result


def snapshot(directory, label):
    directory.mkdir(parents=True, exist_ok=True)
    for file, args in [("threads", ["Thread.print", "-l"]),
                       ("heap", ["GC.heap_info"]),
                       ("native-memory", ["VM.native_memory", "summary", "scale=KB"]),
                       ("jvm-flags", ["VM.flags"])]:
        (directory / f"{label}-{file}.txt").write_text(docker_exec(API, "jcmd", "1", *args), encoding="utf-8")
    (directory / f"{label}-proc-status.txt").write_text(docker_exec(API, "cat", "/proc/1/status"), encoding="utf-8")


class Collector:
    def __init__(self, directory):
        self.directory = directory
        self.stop = threading.Event()
        self.rows = []
        self.errors = []
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stop.is_set():
            started = time.monotonic()
            try:
                row = sample()
                self.rows.append(row)
                with (self.directory / "samples.jsonl").open("a", encoding="utf-8") as out:
                    out.write(json.dumps(row) + "\n")
            except Exception as error:
                self.errors.append(repr(error))
            self.stop.wait(max(0.1, 5 - (time.monotonic() - started)))

    def start(self):
        self.thread.start()

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=30)
        if self.thread.is_alive():
            raise RuntimeError("Collector did not stop")
        (self.directory / "collector-errors.json").write_text(json.dumps(self.errors, indent=2), encoding="utf-8")
        if not self.rows or self.errors:
            raise RuntimeError(f"Incomplete metrics: {self.errors}")
        fields = [k for k in self.rows[0] if k not in ["docker", "generator"]]
        with (self.directory / "resources.csv").open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=fields)
            writer.writeheader()
            writer.writerows({k: row.get(k) for k in fields} for row in self.rows)


def gatling(directory, teams, users, seconds, phase):
    before = set((ROOT / "build/reports/gatling").glob("*"))
    wrapper = str(ROOT / ("gradlew.bat" if os.name == "nt" else "gradlew"))
    args = [wrapper, "--console=plain", "gatlingRun", "--simulation", "com.ildarrash.teamtasks.performance.TaskLifecycleSimulation",
            f"-DbaseUrl={BASE}", f"-Dteams={teams}", f"-Dusers={users}",
            f"-DdurationSeconds={seconds}", f"-DteamBaseId={TEAM_BASE}"]
    log_path = directory / f"{phase}-console.log"
    observer_stop = threading.Event()
    observer_errors = []
    def observe():
        deadline = time.monotonic() + seconds + 180
        while time.monotonic() < deadline and not observer_stop.is_set():
            text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
            if re.search(r"Simulation .* started", text):
                if observer_stop.wait(max(1, seconds/2)):
                    return
                try:
                    captured = int(time.time()*1000)
                    snapshot(directory / "snapshots", "under-load")
                    (directory / "snapshots/under-load-time.json").write_text(json.dumps({"epochMs": captured}), encoding="utf-8")
                except Exception as error:
                    observer_errors.append(repr(error))
                return
            observer_stop.wait(.5)
    observer = threading.Thread(target=observe, daemon=True) if phase == "measurement" else None
    if observer:
        observer.start()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=seconds + 240)
    observer_stop.set()
    if observer:
        observer.join(timeout=30)
        if observer_errors or not (directory / "snapshots/under-load-time.json").exists():
            raise RuntimeError(f"Under-load snapshot missing: {observer_errors}")
    after = set((ROOT / "build/reports/gatling").glob("*"))
    created = after - before
    if len(created) != 1:
        raise RuntimeError(f"Expected one Gatling report, got {created}")
    report = next(iter(created))
    shutil.copytree(report, directory / phase)
    if process.returncode:
        raise RuntimeError(f"Gatling {phase} failed; see {directory / (phase+'-console.log')}")


def run_profile(directory, teams, users, warmup, duration):
    directory.mkdir(parents=True)
    print(f"START teams={teams} users={users}", flush=True)
    command(COMPOSE + ["restart", "api"])
    wait_ready()
    seed(teams)
    snapshot(directory / "snapshots", "cold")
    gatling(directory, teams, users, warmup, "warmup")
    invariant(teams)
    snapshot(directory / "snapshots", "baseline")
    baseline = sample()
    (directory / "baseline.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    docker_exec(API, "jcmd", "1", "VM.native_memory", "baseline")
    docker_exec(API, "jcmd", "1", "JFR.start", "name=benchmark", "settings=profile", "maxsize=128m")
    collector = Collector(directory)
    collector.start()
    try:
        gatling(directory, teams, users, duration, "measurement")
    finally:
        collector.finish()
        docker_exec(API, "jcmd", "1", "JFR.stop", "name=benchmark", "filename=/tmp/benchmark.jfr")
        command(["docker", "cp", f"{API}:/tmp/benchmark.jfr", str(directory / "api.jfr")])
        snapshot(directory / "snapshots", "after")
        (directory / "snapshots/native-memory-diff.txt").write_text(docker_exec(API, "jcmd", "1", "VM.native_memory", "summary.diff", "scale=KB"), encoding="utf-8")
    # A non-GC-forcing histogram is collected AFTER the measured interval.
    (directory / "snapshots/class-histogram.txt").write_text(docker_exec(API, "jcmd", "1", "GC.class_histogram", "-all"), encoding="utf-8")
    (directory / "jfr-summary.txt").write_text(docker_exec(API, "jfr", "summary", "/tmp/benchmark.jfr"), encoding="utf-8")
    events = parse(directory / "measurement/simulation.log")
    (directory / "gatling-events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    proof = invariant(teams)
    (directory / "invariant.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    config = {"teams": teams, "users": users, "seedTasksPerTeam": 10, "warmupSeconds": warmup,
              "measurementSeconds": duration, "teamBaseId": TEAM_BASE,
              "model": "closed constant concurrent users; one complete lifecycle per user",
              "gatling": "3.13.5", "jvmHeap": "Xms256m Xmx512m", "apiCpus": 2, "apiMemoryLimitMiB": 1024}
    (directory / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"PASS teams={teams} users={users}; metrics={len(collector.rows)} samples", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", default="1,10,100,1000")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--extra-users", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--output", default="performance/results/" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()
    teams = [int(t) for t in args.teams.split(",")]
    assert all(0 < t <= 100_000 for t in teams) and args.users > 0 and args.duration > 0 and args.warmup > 0
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / "performance"):
        raise ValueError("Output must be under performance/")
    output.mkdir(parents=True, exist_ok=False)
    command(COMPOSE + ["up", "-d", "--build"])
    wait_ready()
    environment = {
        "sourceRevision": command(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "gitStatusAtRun": command(["git", "status", "--short"]).stdout,
        "docker": command(["docker", "version", "--format", "{{json .}}"] ).stdout,
        "dockerResources": command(["docker", "info", "--format", "{{.NCPU}} CPUs; {{.MemTotal}} bytes memory"]).stdout,
        "apiImage": command(["docker", "inspect", API, "--format", "{{.Image}}"] ).stdout,
        "java": command(["docker", "exec", API, "java", "-version"]).stderr,
        "startedUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (output / "environment.json").write_text(json.dumps(environment, indent=2), encoding="utf-8")
    for count in teams:
        run_profile(output / f"teams-{count}-users-{args.users}", count, args.users, args.warmup, args.duration)
    if args.extra_users:
        run_profile(output / f"teams-{max(teams)}-users-{args.extra_users}", max(teams), args.extra_users, args.warmup, args.duration)
    print(f"COMPLETE {output}", flush=True)
