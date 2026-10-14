"""Build measured resource summaries and Matplotlib charts from retained evidence."""
import argparse
import csv
import html
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MIB = 1024**2


def size(text):
    number, unit = re.match(r"([\d.]+)([A-Za-z]+)", text.strip()).groups()
    factor = {"B": 1, "kB": 1000, "MB": 1000**2, "GB": 1000**3,
              "KiB": 1024, "MiB": MIB, "GiB": 1024**3}[unit]
    return float(number)*factor


def nmt(path):
    text = path.read_text(encoding="utf-8")
    reserved, committed = re.search(r"Total: reserved=(\d+)KB, committed=(\d+)KB", text).groups()
    return {"reservedMiB": int(reserved)/1024, "committedMiB": int(committed)/1024}


def native_stats(path):
    # Gatling's object literal has unquoted identifier keys; preserve quoted values.
    text = path.read_text(encoding="utf-8").split("function fillStats", 1)[0]
    text = text.removeprefix("var stats = ").strip().rstrip(";")
    text = re.sub(r'"(?:\\.|[^"\\])*"|([A-Za-z_$][\w$]*)\s*:',
                  lambda m: json.dumps(m.group(1))+":" if m.group(1) else m.group(0), text)
    return json.loads(text)


def summarise(directory):
    config = json.loads((directory / "config.json").read_text())
    events = json.loads((directory / "gatling-events.json").read_text())
    native = native_stats(directory / "measurement/js/stats.js")
    native_global = native["stats"]
    native_group = next(v["stats"] for v in native["contents"].values() if v["name"] == "Task lifecycle")
    assert int(native_global["numberOfRequests"]["total"]) == events["requests"]
    assert int(native_group["numberOfRequests"]["total"]) == events["successfulTransactions"]
    latency = lambda stats: {f"p{p}": int(stats[f"percentiles{i}"]["total"]) for p,i in [(50,1),(95,3),(99,4)]}
    all_samples = [json.loads(line) for line in (directory / "samples.jsonl").read_text().splitlines()]
    samples = [r for r in all_samples if events["startEpochMs"] <= r["epochMs"] <= events["endEpochMs"]]
    if len(samples) < 2:
        raise AssertionError("Not enough measurement-window samples")
    under_load = json.loads((directory / "snapshots/under-load-time.json").read_text())["epochMs"]
    assert events["startEpochMs"] <= under_load <= events["endEpochMs"], "Snapshot outside request window"
    generators = [s["generator"] for s in samples if s.get("generator") and
                  isinstance(s["generator"].get("rssBytes"), (int, float)) and
                  isinstance(s["generator"].get("osThreads"), (int, float))]
    if not generators:
        raise AssertionError("No generator footprint captured")
    baseline = json.loads((directory / "baseline.json").read_text())
    api_stats = [next(s for s in r["docker"] if s["Name"].endswith("-api-1")) for r in samples]
    db_stats = [next(s for s in r["docker"] if s["Name"].endswith("-db-1")) for r in samples]
    maximum = lambda field: max(r[field] for r in samples)
    summary = {"profile": directory.name, "teams": config["teams"], "users": config["users"],
               "seedTasks": config["teams"]*config["seedTasksPerTeam"],
               "rps": float(native_global["meanNumberOfRequestsPerSecond"]["total"]),
               "tps": float(native_group["meanNumberOfRequestsPerSecond"]["total"]),
               "exactEventWindowRps": events["rps"], "exactEventWindowTps": events["tps"],
               "requests": events["requests"], "httpSeconds": events["observedHttpSeconds"],
               "failedRequests": events["failedRequests"], "failedTransactions": events["failedTransactions"],
               "httpLatencyMs": latency(native_global), "transactionLatencyMs": latency(native_group),
               "sampleCount": len(samples), "baselineJvmLiveThreads": baseline["jvmLiveThreads"],
               "sampledMaxJvmLiveThreads": maximum("jvmLiveThreads"),
               "jvmLifetimePeakThreads": maximum("jvmPeakThreads"),
               "startedThreadsInSampleWindow": samples[-1]["jvmStartedThreads"]-samples[0]["jvmStartedThreads"],
               "sampledMaxOsThreads": maximum("osThreads"),
               "baselineRssMiB": baseline["processRssBytes"]/MIB,
               "sampledMaxRssMiB": maximum("processRssBytes")/MIB,
               "sampledMaxHeapUsedMiB": maximum("heapUsedBytes")/MIB,
               "sampledMaxHeapCommittedMiB": maximum("heapCommittedBytes")/MIB,
               "reportedHeapMaxMiB": maximum("heapMaxBytes")/MIB,
               "sampledMaxApiDockerMemMiB": max(size(s["MemUsage"].split("/")[0]) for s in api_stats)/MIB,
               "sampledMaxDbDockerMemMiB": max(size(s["MemUsage"].split("/")[0]) for s in db_stats)/MIB,
               "sampledMaxApiCpuCorePercent": max(float(s["CPUPerc"].strip("%")) for s in api_stats),
               "sampledMaxDbCpuCorePercent": max(float(s["CPUPerc"].strip("%")) for s in db_stats),
               "sampledMaxDbActiveConnections": maximum("dbActiveConnections"),
               "gcCountInSampleWindow": samples[-1]["gcCount"]-samples[0]["gcCount"],
               "gcPauseSecondsInSampleWindow": samples[-1]["gcTotalSeconds"]-samples[0]["gcTotalSeconds"],
               "generatorSampledMaxRssMiB": max(g["rssBytes"] for g in generators)/MIB,
               "generatorSampledMaxOsThreads": max(g["osThreads"] for g in generators),
               "generatorValidSamples": len(generators),
               "nativeMemoryBaseline": nmt(directory / "snapshots/baseline-native-memory.txt"),
               "nativeMemoryUnderLoad": nmt(directory / "snapshots/under-load-native-memory.txt"),
               "nativeMemoryAfter": nmt(directory / "snapshots/after-native-memory.txt")}
    (directory / "summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    return summary, samples


def render(root):
    profiles = sorted([p for p in root.glob("teams-*-users-*") if p.is_dir()],
                      key=lambda p: (int(p.name.split("-")[1]), int(p.name.split("-")[3])))
    summaries, windows = zip(*(summarise(p) for p in profiles))
    (root / "summary.json").write_text(json.dumps(summaries, indent=2)+"\n", encoding="utf-8")
    fields = [k for k, v in summaries[0].items() if not isinstance(v, dict)]
    with (root / "summary.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: s[k] for k in fields} for s in summaries)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    labels = [f'{s["teams"]} teams\n{s["users"]} users' for s in summaries]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    axes[0,0].bar(labels, [s["rps"] for s in summaries], color="#2463a6")
    axes[0,0].set_title("HTTP throughput (successful requests/s)")
    axes[0,1].bar(labels, [s["tps"] for s in summaries], color="#268264")
    axes[0,1].set_title("Completed four-request lifecycles/s")
    axes[1,0].plot(labels, [s["httpLatencyMs"]["p95"] for s in summaries], "o-", label="HTTP p95")
    axes[1,0].plot(labels, [s["transactionLatencyMs"]["p95"] for s in summaries], "o-", label="Lifecycle p95")
    axes[1,0].set_title("Latency, ms (native Gatling percentiles)")
    axes[1,0].legend()
    axes[1,1].plot(labels, [s["sampledMaxRssMiB"] for s in summaries], "o-", label="API RSS")
    axes[1,1].plot(labels, [s["sampledMaxHeapUsedMiB"] for s in summaries], "o-", label="API heap used")
    axes[1,1].plot(labels, [s["sampledMaxDbDockerMemMiB"] for s in summaries], "o-", label="DB container")
    axes[1,1].set_title("Sampled memory maxima, MiB")
    axes[1,1].legend()
    fig.suptitle("Gatling comparison | 10 seed tasks/team | API 2 CPUs / 1 GiB | Xmx512m")
    fig.savefig(root / "comparison.png", dpi=160)
    fig.savefig(root / "comparison.svg")
    plt.close(fig)
    for profile, summary, samples in zip(profiles, summaries, windows):
        epoch = samples[0]["epochMs"]
        times = [(r["epochMs"]-epoch)/1000 for r in samples]
        fig, axes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
        axes[0].plot(times, [r["heapUsedBytes"]/MIB for r in samples], "o-", label="Heap used")
        axes[0].plot(times, [r["heapCommittedBytes"]/MIB for r in samples], "o-", label="Heap committed")
        axes[0].plot(times, [r["processRssBytes"]/MIB for r in samples], "o-", label="Process RSS")
        axes[0].set_ylabel("MiB")
        axes[0].legend()
        axes[1].plot(times, [r["jvmLiveThreads"] for r in samples], "o-", label="JVM live threads")
        axes[1].plot(times, [r["osThreads"] for r in samples], "o-", label="OS threads")
        axes[1].set_ylabel("Threads")
        axes[1].set_xlabel("Seconds from first in-window sample (5s target cadence)")
        axes[1].legend()
        fig.suptitle(f'{summary["teams"]} teams / {summary["users"]} users | request-window samples only')
        fig.savefig(profile / "resources.png", dpi=150)
        fig.savefig(profile / "resources.svg")
        plt.close(fig)
    table = "".join(f'<tr><td>{s["teams"]}</td><td>{s["users"]}</td><td>{s["rps"]:.2f}</td>'
                    f'<td>{s["tps"]:.2f}</td><td>{s["httpLatencyMs"]["p95"]}</td>'
                    f'<td>{s["sampledMaxJvmLiveThreads"]:.0f}</td><td>{s["sampledMaxRssMiB"]:.1f}</td>'
                    f'<td><a href="{s["profile"]}/measurement/index.html">Gatling HTML</a> · '
                    f'<a href="{s["profile"]}/resources.png">Resources</a> · '
                    f'<a href="{s["profile"]}/snapshots/under-load-threads.txt">Threads</a> · '
                    f'<a href="{s["profile"]}/api.jfr">JFR</a></td></tr>' for s in summaries)
    footprints = ""
    for s in summaries:
        values = [
            ("JVM live / OS threads sampled maximum", f'{s["sampledMaxJvmLiveThreads"]:.0f} / {s["sampledMaxOsThreads"]:.0f}'),
            ("JVM threads started between first/last in-window samples", f'{s["startedThreadsInSampleWindow"]:.0f}'),
            ("Heap used / committed sampled maximum", f'{s["sampledMaxHeapUsedMiB"]:.1f} / {s["sampledMaxHeapCommittedMiB"]:.1f} MiB'),
            ("Configured Xmx", "512 MiB"),
            ("Process RSS / Docker working-set sampled maximum", f'{s["sampledMaxRssMiB"]:.1f} / {s["sampledMaxApiDockerMemMiB"]:.1f} MiB'),
            ("NMT total committed / reserved under-load snapshot", f'{s["nativeMemoryUnderLoad"]["committedMiB"]:.1f} / {s["nativeMemoryUnderLoad"]["reservedMiB"]:.1f} MiB (includes heap)'),
            ("PostgreSQL container memory sampled maximum", f'{s["sampledMaxDbDockerMemMiB"]:.1f} MiB'),
            ("API / DB CPU sampled maximum", f'{s["sampledMaxApiCpuCorePercent"]:.1f}% / {s["sampledMaxDbCpuCorePercent"]:.1f}% of one core'),
            ("GC count / pause time between in-window samples", f'{s["gcCountInSampleWindow"]:.0f} / {s["gcPauseSecondsInSampleWindow"]:.4f}s'),
            ("Gatling generator RSS / OS threads sampled maximum", f'{s["generatorSampledMaxRssMiB"]:.1f} MiB / {s["generatorSampledMaxOsThreads"]:.0f}'),
        ]
        rows = "".join(f'<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>' for k,v in values)
        footprints += f'<details><summary>{s["teams"]} teams / {s["users"]} users — full resource footprint</summary><table>{rows}</table><img src="{s["profile"]}/resources.png" alt="Memory and thread timeline"></details>'
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Gatling performance evidence</title>
<style>body{{font:16px system-ui;max-width:1200px;margin:40px auto;padding:0 24px;color:#182b3e}}h1{{font-size:30px}}table{{border-collapse:collapse;width:100%}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #ccd5df}}a{{color:#2463a6}}img{{width:100%}}.note{{background:#eef4fa;padding:16px;line-height:1.6}}</style>
<h1>Gatling performance evidence</h1><p>1 / 10 / 100 / 1000 teams · 10 seed tasks/team · 30s warmup + 60s measurement</p>
<table><tr><th>Teams</th><th>Users</th><th>RPS</th><th>TPS</th><th>HTTP p95 ms</th><th>JVM live max*</th><th>RSS MiB*</th><th>Evidence</th></tr>{table}</table>
<p class="note">TPS = complete POST → priority PATCH → GET list → DELETE lifecycles. RPS, TPS and latency match native Gatling HTML statistics. Exact first-request-start to last-response-end rates are retained separately in JSON. * Resource maxima are sampled, not exact lifetime maxima. JVM live threads differ from virtual users and OS threads. RSS differs from heap and Docker working-set memory. All measurements are local, instrumented and single-pass; no production SLA is inferred.</p>
<img src="comparison.png" alt="Gatling throughput, latency and footprint comparison">
<h2>Thread and memory snapshots</h2>{footprints}
<p><a href="summary.json">Machine-readable summaries</a> · <a href="summary.csv">CSV</a> · <a href="environment.json">Environment</a></p></html>'''
    (root / "index.html").write_text(page, encoding="utf-8")
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    summaries = render(args.directory)
    print(json.dumps([{k: s[k] for k in ["teams", "users", "rps", "tps", "sampledMaxJvmLiveThreads", "sampledMaxRssMiB"]} for s in summaries], indent=2))
