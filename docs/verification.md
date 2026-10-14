# Local verification

Date: 2026-10-14, Europe/Budapest. Local implementation; no remote repository changes.

## Build and database tests

- Windows host JDK 17.0.1; Gradle wrapper 8.13; Spring Boot 3.5.7; Kotlin 2.1.20.
- Docker Desktop 4.26.1 / Engine 24.0.7 with Linux containers; PostgreSQL 16.14 from postgres:16-alpine.
- `RUN_POSTGRES_INTEGRATION=true ./gradlew.bat --no-daemon test bootJar`: successful; 11 tests, 0 failures, 0 errors, 0 skipped.
- Real PostgreSQL integration tests use two independent service instances, parallel writes and snapshot readers. This verifies shared DB locking; it is not a production or distributed deployment test.
- Docker multi-stage bootJar build successful on Linux JDK 17; API starts with Flyway schema validated and health UP.

## HTTP acceptance

`python scripts/verify_api.py --base http://127.0.0.1:8080 --output output/acceptance-ipv4.json`: passed in 2.304 seconds before cleanup.

- Independent teams and server-assigned priority.
- Upward/downward/no-op moves; preserved relative order.
- Validation, immutable fields and standard error response.
- Middle/first/last/final deletions and re-creation at priority 1.
- 40 concurrent HTTP creations; unique ids and dense priorities.
- 120 mixed concurrent writes and consistent snapshot reads.

An earlier probe was interrupted by container replacement during image rebuild; it is excluded from acceptance evidence. The later probe targets the completed image. Windows Python localhost initially added about 2 seconds per connection through IPv6 fallback; 127.0.0.1 avoids that client artefact.

## Root review

Bounded source review performed by root; no claim of an independent isolated reviewer. Reviewed parameterized SQL, lock acquisition before reads used for writes, re-reading by id after lock, deferred unique constraint, atomic range shifts, validation/null/unknown-field semantics, safe error responses and limited rollback retry. No remote auth, deployment or HR messaging performed.

OpenAPI YAML and all local references parsed using SnakeYAML from the build dependencies. Python scripts parsed for syntax. Archive packaging preserves Git executable mode for gradlew, excludes .git/build/volumes/secrets and selects only tracked files.

## Historical Python load measurements

The previous Python generator has been removed. Its original report is retained at performance/historical/python-load.json. Both previous scenarios passed. Docker reported 16 CPUs and 16,741,457,920 bytes available memory. Client: Windows10 / Python3.12.14. The canonical load suite is now [Gatling](../performance/README.md); its dataset, resource limits and instrumentation differ, so these older rates must not be compared directly.

| Scenario | Successful four-request workflows | HTTP requests/s | Workflow latency p50 / p95 / p99 ms | Unexpected errors |
|---|---:|---:|---|---:|
| One team | 6468 | 430.34 | 177.53 / 269.50 / 313.86 | 0 |
| Ten teams | 19277 | 1283.87 | 58.15 / 89.83 / 125.54 | 0 |

Each measurement ran for about 60 seconds after 30 seconds warmup with 20 users. Every workflow lists and verifies dense priorities; final per-team invariants passed. Latency covers the whole POST/move/list/DELETE workflow. The earlier slow localhost acceptance run finished during the first load scenario; it used separate teams and adds a small unquantified local background workload to that scenario. Counts cover successful measured workflows, excluding warmup.

## Restart and archive

- `python scripts/restart_test.py`: all task fields preserved after API restart.
- `python scripts/restart_test.py --recreate --output output/persistence.json`: checks container recreation through down/up without deleting the DB volume; result recorded in verification-results/persistence.json.
- Archive paths/exclusions and Unix executable metadata for gradlew checked. Unpacked sources successfully ran `gradlew.bat --no-daemon test bootJar` with a fresh build directory and shared dependency cache: 9 unit tests passed, 2 DB tests explicitly skipped. DB integration evidence comes from the earlier enabled run, not this archive unit-only build.
- Linux Docker build and Windows host/archive build verified; macOS and a clean machine without dependency caches were not tested.

Raw HTTP and restart reports are retained in [verification-results](verification-results/). The historical Python report moved to performance/historical/. Canonical Gatling and profiling results live in performance/results/. Earlier failures were fixed or excluded with reasons above; no synthetic successful report was substituted.
