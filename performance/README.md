# Native performance and exact thread births

This is a native-only local Gatling suite. It runs the Native Image API through `strace -ff` and records successful Linux `clone`/`clone3` calls with `CLONE_THREAD`, alongside HTTP throughput, latency, RSS, sampled thread concurrency, Docker CPU/memory, and raw Gatling reports.

Build the Native Image, then the traced performance image:

```sh
docker build -t team-tasks-api-native .
docker compose -p team-tasks-native-performance -f performance/compose.yaml build api
```

Prerequisites: Docker running Linux containers, Python 3.10+, and JDK 17 with `JAVA_HOME` set for host-side Gatling. Building the API image does not need a host JDK.

Run the five-profile matrix (1/20, 10/20, 100/20, 1000/20, 1000/100 teams/users; 30s warmup and 60s measurement):

```sh
python performance/run_native.py
```

The runner prints a fresh UTC output directory such as `performance/results/native-YYYYMMDDTHHMMSSffffffZ`. Verify and render that exact printed path:

```sh
python performance/verify_results.py performance/results/native-YYYYMMDDTHHMMSSffffffZ
python performance/render_native.py performance/results/native-YYYYMMDDTHHMMSSffffffZ
```

The bundled `performance/results/native` evidence remains available for reference. To choose a new explicit directory, use a new unused name:

```sh
python performance/run_native.py --output performance/results/native-local-20261015
python performance/verify_results.py performance/results/native-local-20261015
python performance/render_native.py performance/results/native-local-20261015
```

For a short workflow check, use two users with a 2s warmup and 10s measurement:

```sh
python performance/run_native.py --smoke2users --output performance/results/native-smoke-local
```

The suite owns Docker project `team-tasks-native-performance`, port 8084, and its PostgreSQL volume. API and DB each use 2 CPUs and 1 GiB; the API receives `-Xms256m -Xmx512m`. It adds no capabilities, privileged mode, or seccomp exception.

`exactStartedOsThreads` is an exact birth count only when conservative Docker-Linux/Gatling clock bounds leave no ambiguous clone syscall at a measurement boundary. The runner aborts that profile otherwise. Warmup may be ambiguous and is then recorded as `null` with its full bounds in `threadCountValidation`. Failed and non-thread clone calls are retained but excluded. The initial application main thread is excluded because it was not created by a traced clone. `exactTotalStartedOsThreads` includes API-thread-group births from startup through trace copy, including fixture seeding and warmup; it is not limited to the 60-second measurement. Five-second `/proc` samples are only an observed RSS/concurrency peak.

Each profile retains Gatling HTML/logs, binary `simulation.log`, cloned strace files, parsed trace evidence, clock samples, process/RSS/thread samples, Docker statistics, configuration, and summary JSON. The runner does not overwrite nonempty output directories.

The rendered native evidence is [report.md](results/native/report.md) and [index.html](results/native/index.html). Gatling compiles its simulation automatically; the production image compiles the application source itself.
