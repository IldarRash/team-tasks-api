"""Matched JVM/Native Image load comparison; common OS metrics, no JVM-only profiling during load."""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import run_suite as suite
from parse_gatling import parse
from stats_support import native_stats

ROOT = suite.ROOT
COMPOSE = ["docker", "compose", "-p", "team-tasks-compare", "-f", str(ROOT / "performance/compare-compose.yaml")]
suite.COMPOSE = COMPOSE
suite.DB = "team-tasks-compare-db-1"
suite.BASE = "http://127.0.0.1:8082"
MIB = 1024**2


def measure_os():
    row = {"epochMs": int(time.time()*1000)}
    for line in suite.docker_exec(suite.API, "cat", "/proc/1/status").splitlines():
        if line.startswith("VmRSS:"):
            row["rssBytes"] = int(line.split()[1])*1024
        if line.startswith("Threads:"):
            row["osThreads"] = int(line.split()[1])
    stats = suite.command(["docker", "stats", "--no-stream", "--format", "{{json .}}", suite.API, suite.DB]).stdout
    row["containers"] = [json.loads(line) for line in stats.splitlines() if line.strip()]
    row['osThreadIds'] = [int(t) for t in suite.docker_exec(suite.API,'ls','/proc/1/task').split()]
    row["generator"] = suite.generator_process()
    return row


class OsCollector:
    def __init__(self, path):
        self.path, self.rows, self.errors = path, [], []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stop.is_set():
            started = time.monotonic()
            try:
                row = measure_os()
                self.rows.append(row)
                with self.path.open("a", encoding="utf-8") as out:
                    out.write(json.dumps(row)+"\n")
            except Exception as error:
                self.errors.append(repr(error))
            self.stop.wait(max(.1,5-(time.monotonic()-started)))

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=30)
        assert not self.thread.is_alive() and not self.errors and self.rows, self.errors


def load(directory, teams, users, seconds, phase):
    before = set((ROOT / "build/reports/gatling").glob("*"))
    wrapper = str(ROOT / ("gradlew.bat" if os.name == "nt" else "gradlew"))
    args = [wrapper,"--console=plain","gatlingRun","--simulation","com.ildarrash.teamtasks.performance.TaskLifecycleSimulation",
            f"-DbaseUrl={suite.BASE}",f"-Dteams={teams}",f"-Dusers={users}",f"-DdurationSeconds={seconds}",f"-DteamBaseId={suite.TEAM_BASE}"]
    with (directory/f"{phase}-console.log").open("w",encoding="utf-8") as out:
        result = subprocess.run(args,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,timeout=seconds+240)
    created = set((ROOT / "build/reports/gatling").glob("*"))-before
    assert len(created)==1, (result.returncode,created)
    report = next(iter(created))
    import shutil
    shutil.copytree(report,directory/phase)
    assert result.returncode==0, directory/f"{phase}-console.log"


def run(directory, runtime, teams, users, warmup, seconds):
    print(f"START {runtime} teams={teams} users={users}",flush=True)
    directory.mkdir(parents=True, exist_ok=True)
    suite.API = f"team-tasks-compare-{runtime}-1"
    suite.command(COMPOSE+["stop","jvm","native"],check=False)
    start=time.perf_counter()
    suite.command(COMPOSE+["up","-d",runtime])
    suite.wait_ready()
    startup=time.perf_counter()-start
    startup_logs = suite.command(['docker','logs',suite.API]).stdout
    (directory/'startup.log').write_text(startup_logs,encoding='utf-8')
    boot_time = re.search(r'Started TeamTasksApplicationKt in ([\d.]+) seconds', startup_logs)
    (directory/'process-startup.txt').write_text(suite.docker_exec(suite.API,'cat','/proc/1/status'),encoding='utf-8')
    if runtime == 'jvm':
        version = suite.command(['docker','exec',suite.API,'java','-version'])
        (directory/'runtime-version.txt').write_text(version.stdout+version.stderr,encoding='utf-8')
        (directory/'runtime-flags.txt').write_text(suite.docker_exec(suite.API,'jcmd','1','VM.flags'),encoding='utf-8')
    suite.sql(f"DELETE FROM tasks WHERE team_id >= {suite.TEAM_BASE} AND team_id < {suite.TEAM_BASE+1000}; DELETE FROM team_locks WHERE team_id >= {suite.TEAM_BASE} AND team_id < {suite.TEAM_BASE+1000};")
    suite.seed(teams)
    suite.sql("VACUUM (ANALYZE) tasks; VACUUM (ANALYZE) team_locks;")
    load(directory,teams,users,warmup,"warmup")
    suite.invariant(teams)
    baseline=measure_os()
    (directory/"baseline.json").write_text(json.dumps(baseline,indent=2))
    collector=OsCollector(directory/"samples.jsonl")
    collector.thread.start()
    try:
        load(directory,teams,users,seconds,"measurement")
    finally:
        collector.finish()
    proof=suite.invariant(teams)
    events=parse(directory/"measurement/simulation.log")
    (directory/"events.json").write_text(json.dumps(events,indent=2))
    stats=native_stats(directory/"measurement/js/stats.js")
    global_stats=stats['stats']
    group=next(s['stats'] for s in stats['contents'].values() if s['name']=='Task lifecycle')
    samples=[s for s in collector.rows if events['startEpochMs']<=s['epochMs']<=events['endEpochMs']]
    assert len(samples)>=max(1,seconds//10)
    assert int(global_stats['numberOfRequests']['total'])==events['requests']
    assert int(group['numberOfRequests']['total'])==events['successfulTransactions']
    rss=max(s['rssBytes'] for s in samples)/MIB
    cpu=max(float(c['CPUPerc'].strip('%')) for s in samples for c in s['containers'] if c['Name']==suite.API)
    summary={"rps":float(global_stats['meanNumberOfRequestsPerSecond']['total']),
             "tps":float(group['meanNumberOfRequestsPerSecond']['total']),
             "httpP95Ms":int(global_stats['percentiles3']['total']),
             "transactionP95Ms":int(group['percentiles3']['total']),
             "rssMiB":rss,"osThreads":max(s['osThreads'] for s in samples),"cpuPercent":cpu,
             "observedNewOsThreads":len(set(t for s in samples for t in s['osThreadIds'])-set(baseline['osThreadIds'])),
             "observedNewOsThreadsDefinition":"Distinct OS thread IDs first observed in 5s samples since post-warmup baseline; lower bound, excludes threads born and ended between samples",
             "generatorValidSamples":sum(s['generator'] is not None for s in samples),
             "generatorRssMiB":max((s['generator']['rssBytes']/MIB for s in samples if s['generator']),default=None),
             "generatorOsThreads":max((s['generator']['osThreads'] for s in samples if s['generator']),default=None),
             "startupSeconds":startup,"startupDefinition":"Docker compose up through first healthy HTTP response; includes container orchestration and 1s polling", "errors":events['failedRequests'],
             "applicationStartupSeconds":float(boot_time.group(1)) if boot_time else None,
             "reportPath":str(directory.relative_to(directory.parents[1])).replace('\\','/')+'/measurement/index.html',
             "requestCount":events['requests'],"sampleCount":len(samples),"runtime":runtime,
             "teams":teams,"users":users,"warmupSeconds":warmup,"measurementSeconds":seconds,
             "invariant":proof,"jvmOnlyDiagnostics":"not collected in either timed run for comparability"}
    (directory/"summary.json").write_text(json.dumps(summary,indent=2)+'\n')
    (directory/"process-after.txt").write_text(suite.docker_exec(suite.API,'cat','/proc/1/status'))
    (directory/"container.json").write_text(suite.command(['docker','inspect',suite.API]).stdout)
    print(f"PASS {runtime} teams={teams} users={users}: {summary['rps']:.2f} RPS; RSS {rss:.1f}MiB",flush=True)
    return summary


def resume_summary(directory, runtime, teams, users, warmup, duration):
    summary_path = directory / 'summary.json'
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        expected = {
            'runtime': runtime, 'teams': teams, 'users': users,
            'warmupSeconds': warmup, 'measurementSeconds': duration,
        }
        actual = {key: summary.get(key) for key in expected}
        if actual != expected:
            raise ValueError(
                f'Existing {directory} has a different configuration; select a fresh output directory'
            )
        return summary
    if directory.exists() and any(directory.iterdir()):
        raise ValueError(
            f'Refusing to overwrite incomplete runtime evidence in {directory}; select a fresh output directory'
        )
    return None


def validate_existing_comparison(payload, requested_config):
    recorded = payload.get('runConfig')
    if recorded is not None:
        if recorded != requested_config:
            raise ValueError('Existing comparison uses a different configuration; select a fresh output directory')
        return

    methodology = payload.get('methodology', {})
    if (methodology.get('warmupSeconds'), methodology.get('measurementSeconds')) != (
        requested_config['warmupSeconds'], requested_config['measurementSeconds']
    ):
        raise ValueError('Existing comparison uses different durations; select a fresh output directory')
    expected_profiles = requested_config['profiles']
    existing_profiles = payload.get('profiles', [])
    if len(existing_profiles) > len(expected_profiles):
        raise ValueError('Existing comparison has a different profile matrix; select a fresh output directory')
    for existing, expected in zip(existing_profiles, expected_profiles):
        if (existing.get('teams'), existing.get('users')) != (expected['teams'], expected['users']):
            raise ValueError('Existing comparison has a different profile matrix; select a fresh output directory')
        present = sorted(runtime for runtime in ('jvm', 'native') if existing.get(runtime) is not None)
        if present != requested_config['runtimes']:
            raise ValueError('Existing comparison uses different runtimes; select a fresh output directory')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output')
    parser.add_argument('--warmup',type=int,default=30)
    parser.add_argument('--duration',type=int,default=60)
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--runtimes',default='jvm,native')
    args=parser.parse_args()
    runtimes = args.runtimes.split(',')
    if not runtimes or any(runtime not in ('jvm', 'native') for runtime in runtimes) or len(set(runtimes)) != len(runtimes):
        parser.error('--runtimes must be a comma-separated, non-repeating subset of jvm,native')
    if args.warmup <= 0 or args.duration <= 0:
        parser.error('--warmup and --duration must be positive seconds')
    profiles=[(1,2)] if args.smoke else [(1,20),(10,20),(100,20),(1000,20),(1000,100)]
    requested_config = {
        'profiles': [{'teams': teams, 'users': users} for teams, users in profiles],
        'runtimes': sorted(runtimes), 'warmupSeconds': args.warmup, 'measurementSeconds': args.duration,
    }
    if args.output:
        output=(ROOT/args.output).resolve()
    else:
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        output = ROOT / 'performance/results' / f'jvm-native-comparison-{stamp}'
    if not output.is_relative_to(ROOT/'performance'):
        parser.error('--output must be under performance/')
    comparison_path = output / 'comparison.json'
    existing_payload = None
    if output.exists():
        if not args.output:
            raise ValueError(f'Fresh default output already exists: {output}')
        if comparison_path.exists():
            existing_payload = json.loads(comparison_path.read_text(encoding='utf-8'))
            validate_existing_comparison(existing_payload, requested_config)
        elif any(output.iterdir()):
            raise ValueError(f'Refusing to overwrite existing output without comparison.json: {output}')
    else:
        output.mkdir(parents=True)
    print(f'OUTPUT {output}', flush=True)

    resumed = {}
    for teams, users in profiles:
        for runtime in runtimes:
            directory = output / f'teams-{teams}-users-{users}' / runtime
            resumed[(teams, users, runtime)] = resume_summary(
                directory, runtime, teams, users, args.warmup, args.duration
            )
    has_work = any(summary is None for summary in resumed.values())
    if has_work:
        suite.command(COMPOSE+['up','-d','db'])
        suite.command(COMPOSE+['build','jvm'])
        info = json.loads(suite.command(['docker','info','--format','{{json .}}']).stdout)
        payload={
            'profiles': [], 'runConfig': requested_config,
            'methodology': {'warmupSeconds':args.warmup,'measurementSeconds':args.duration,
                            'seedTasksPerTeam':10,'cpuLimit':2,'memoryLimitMiB':1024,'heapMaxMiB':512},
            'generatedAt': (existing_payload or {}).get('generatedAt', dt.datetime.now(dt.timezone.utc).isoformat()),
            'environment': {key:info.get(key) for key in ['NCPU','MemTotal','OSType','OperatingSystem','ServerVersion']},
        }
    else:
        payload = existing_payload
    for profile_index,(teams,users) in enumerate(profiles):
        pair={'teams':teams,'users':users,'jvm':None,'native':None}
        profile_runtimes = list(runtimes)
        if profile_index % 2 and set(profile_runtimes)=={'jvm','native'}:
            profile_runtimes.reverse()
        for runtime in profile_runtimes:
            directory=output/f'teams-{teams}-users-{users}'/runtime
            summary = resumed[(teams, users, runtime)]
            if summary is not None:
                pair[runtime] = summary
                print(f'RESUME {runtime} teams={teams} users={users}', flush=True)
            else:
                pair[runtime]=run(directory,runtime,teams,users,args.warmup,args.duration)
        if has_work:
            payload['profiles'].append(pair)
            comparison_path.write_text(json.dumps(payload,indent=2)+'\n')
    print(f'COMPLETE {output}',flush=True)
