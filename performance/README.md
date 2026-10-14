# Gatling performance suite

Gatling generates HTTP load. Python scripts only orchestrate containers, capture diagnostics and turn actual evidence into comparison charts. The old Python load generator was removed; its previous numbers are retained in historical/python-load.json and are not comparable to this suite's constrained/instrumented environment.

## Approved matrix

| Teams | Seed tasks/team | Active virtual users | Warmup | Measurement |
|---:|---:|---:|---:|---:|
| 1 | 10 | 20 | 30s | 60s |
| 10 | 10 | 20 | 30s | 60s |
| 100 | 10 | 20 | 30s | 60s |
| 1000 | 10 | 20 | 30s | 60s |
| 1000 | 10 | 100 | 30s | 60s |

Closed workload: constant concurrent users, one full lifecycle per user, replaced immediately when completed. Teams are selected globally round-robin. Each lifecycle executes POST /tasks → PATCH priority to 1 → GET team tasks → DELETE own task. Checks require 201/200/200/204, correct team/id, valid priorities and zero failed requests/groups. Warmup runs in a separate Gatling invocation and does not enter measured throughput/latency.

## Reproduce

Prerequisites: JDK17 with JAVA_HOME set correctly, Docker with Linux containers, Python3.10+, internet for the first dependency/image download. Ports 8081 must be free. The regular application's port 8080 and database are left untouched. Benchmark containers use the separate project team-tasks-benchmark and a separate DB volume.

```sh
./gradlew bootJar gatlingClasses
python performance/run_suite.py
python -m pip install -r performance/requirements.txt
python performance/render_results.py performance/results/RUN_DIRECTORY
```

PowerShell uses `.\gradlew.bat` instead of `./gradlew`. The suite prints its output directory; the rendering command takes that exact directory. Rendering only needs Matplotlib; the generator, sampler and binary-event reader use the standard library. The suite defaults to all five approved profiles. It does not publish anything or delete volumes.

Short capability smoke:

```sh
python performance/run_suite.py --teams 1 --users 2 --extra-users 0 --warmup 2 --duration 5 --output performance/work/my-smoke
```

An output directory must be new; existing evidence is never overwritten. To change the matrix use --teams, --users, --extra-users, --warmup, --duration. --extra-users 0 disables the extra profile. The runner only allows output under performance/. Avoid running multiple suites concurrently: they intentionally share one bounded benchmark fixture range.

Standalone Gatling after the benchmark containers/fixtures have been prepared:

```sh
./gradlew gatlingRun --simulation com.ildarrash.teamtasks.performance.TaskLifecycleSimulation -DbaseUrl=http://127.0.0.1:8081 -Dteams=1000 -Dusers=20 -DdurationSeconds=60 -DteamBaseId=7000000000000
```

The benchmark image copies build/libs/team-tasks-api.jar, so rebuild bootJar after changing production code. Stop its containers with `docker compose -p team-tasks-benchmark -f performance/compose.yaml down`. The dedicated volume remains for reproducibility; never add -v unless you explicitly intend to erase benchmark data.

## Controlled runtime

- API: 2 CPUs, 1GiB container limit; heap Xms256m/Xmx512m; ActiveProcessorCount=2; NativeMemoryTracking=summary.
- PostgreSQL: 2 CPUs, 1GiB limit. Each profile re-seeds its 10 tasks/team in the dedicated benchmark DB. API JVM restarts per profile; DB volume/cache persists across sequential profiles.
- JDK17's actual GC/flags are recorded in snapshots; this setup selects SerialGC ergonomically. No claim is made about another collector or unconstrained production runtime.
- Gatling3.13.5 / Gradle plugin3.13.5.3, Java17, generator Xms256m/Xmx512m; Netty event loops fixed at 8. Gatling3.14.9's plugin requires a newer Java runtime and was not used.
- Gatling generator runs on the Windows host; API and PostgreSQL run in local Linux containers. The host CPU/memory and image digest are recorded in environment.json. This is a single local pass per profile, not a statistically repeated production capacity estimate.

## What is retained

Each successful profile contains:

- measurement/index.html and all native Gatling report assets; simulation.log is Gatling3.13.5's binary event stream. warmup/ is retained separately.
- gatling-events.json: decoded successful/failed HTTP and group counts, per-endpoint latency, lifecycle latency and request timestamps.
- samples.jsonl and resources.csv: actual JVM counters plus container/process measurements at a target 5-second cadence. Comparison uses only samples whose timestamps lie in the measured HTTP interval.
- snapshots/: cold, warmed baseline, under-load and after thread dumps, heap summaries, native-memory summaries and JVM flags; native-memory diff and after-run class histogram.
- api.jfr and jfr-summary.txt: genuine JDK Flight Recorder data, including allocation/GC/thread/CPU events according to profile settings.
- config.json, invariant.json, baseline.json, console logs and summary.json.
- resources.png/.svg: measured memory and thread timeline. Comparison PNG/SVG, CSV/JSON and an HTML evidence index live at run-directory level.

Snapshot times are explicit. Thread dumps/NMT/heap commands run sequentially, so they are nearby observations, not one atomic state. Class histogram is collected after measurement with -all; full .hprof heap dumps are not produced during timed load. Open api.jfr in JDK Mission Control for deeper allocation/thread analysis.

## Metric definitions and limits

Primary RPS/TPS and percentiles are copied from native Gatling statistics, so the comparison matches its HTML reports. TPS refers to successful four-request lifecycle groups, not SQL transaction rate. Gatling normalises throughput over whole-second reporting buckets; a separate exact first-request-start to last-response-end calculation is retained as exactEventWindowRps/exactEventWindowTps in summary.json. gatling-events.json also contains raw-event nearest-rank percentiles. Those can differ slightly from Gatling's histogram percentiles. Count-check requires exactly four HTTP events per completed group.

Virtual users are concurrent asynchronous sessions, not dedicated threads. JVM live threads, JVM lifetime peak, started-thread counter delta and OS thread count are reported separately. Started-thread delta and GC totals are observed between first/last in-window samples; very short-lived activity between samples may be missed by the timeline, while JFR provides additional event evidence.

Heap used, heap committed, configured Xmx, JVM native committed/reserved, process RSS and Docker working-set memory describe different things. NMT totals include the Java heap; never add them to heap figures. Reserved memory is virtual address space, not physical RAM consumed. Pool-level heap maxima can differ slightly from configured Xmx because of GC pool accounting. Sampled maxima are not exact lifetime memory peaks.

Docker CPU percentage is relative to one core; 200% means about two cores, the configured container allocation. PostgreSQL memory and Gatling generator RSS/OS threads are also sampled. Generator observations missing because its process exited during a boundary sample are excluded from its maxima; generatorValidSamples records coverage. All raw samples are retained. Actuator requests, docker stats, jcmd, JFR/NMT and host-process observation add overhead; it is present for every profile. Warmup is30 seconds, measurements are60 seconds, and database caches/bloat/order can still influence a single pass. These profiles compare team cardinality and20 vs100-user contention; they do not prove performance for large lists, millions of stored tasks, long soak duration or separate production machines.

Retained run: [2026-10-14 comparison](results/20261014-gatling/index.html), [machine-readable summary](results/20261014-gatling/summary.json).

References: [Gatling Gradle](https://docs.gatling.io/integrations/build-tools/gradle-plugin/), [workload injection](https://docs.gatling.io/concepts/injection/), [binary log source](https://github.com/gatling/gatling/blob/v3.13.5/gatling-core/src/main/scala/io/gatling/core/stats/writer/LogFileDataWriter.scala), [JDK17 diagnostics](https://docs.oracle.com/en/java/javase/17/docs/specs/man/jcmd.html).
