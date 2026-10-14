# JVM and GraalVM Native Image: measured comparison

Gatling generates the load. One TPS is one successful lifecycle of four HTTP requests.

| Teams | Users | Runtime | RPS | TPS | HTTP p95 ms | Lifecycle p95 ms | RSS MiB | OS threads | Errors |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2 | jvm | 297.20 | 74.30 | 10 | 39 | 286.1 | 33 | 0 |
| 1 | 2 | native | 213.45 | 53.36 | 16 | 51 | 196.8 | 20 | 0 |

Observed changes, Native relative to JVM (one pass per profile):

| Teams | Users | RPS change | RSS change | HTTP p95 change |
|---:|---:|---:|---:|---:|
| 1 | 2 | -28.2% | -31.2% | +60.0% |

Both API variants have 2 CPUs, 1 GiB container memory and a 512 MiB maximum heap. PostgreSQL has matching 2 CPU / 1 GiB limits. Ten tasks per team are reset before each run. Warmup is separate from measurement. Each runtime gets a fresh process. Gatling uses the same shared keep-alive connection pool across virtual users for both runtimes. Execution order alternates between JVM-first and Native-first across profiles.

RSS, OS threads, container CPU/memory and the Gatling generator footprint are sampled every five seconds. Values are observed maxima, not exact lifetime peaks. JVM-only JFR/NMT profiling is absent from both timed variants. Separate diagnostic captures are not used as the paired baseline.

Throughput and latency use Gatling native report statistics. TPS is not the database transaction rate. Virtual users are asynchronous sessions and do not correspond to a dedicated thread each. Docker CPU 200% corresponds to two cores.

Startup measures Docker compose up through the first healthy HTTP response and includes orchestration plus one-second polling. Database caches, sequential execution order and shared host scheduling can affect a single pass. Results describe this local workload, not a production capacity guarantee.

[Interactive dashboard](index.html) · [Raw comparison](comparison.json)

## Additional footprints

| Teams | Users | Runtime | App startup s | Docker-to-health s | New OS thread IDs observed | Generator RSS MiB | Generator threads |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 2 | jvm | 7.392 | 6.86 | 0 | 256.0 | 67 |
| 1 | 2 | native | 0.473 | 2.27 | 0 | 264.7 | 68 |

New thread IDs are distinct Linux thread IDs first seen in the measurement samples relative to the post-warmup baseline. Threads that start and finish between snapshots are not counted. Generator samples can be missing at process exit; sample coverage is retained in each summary.

## Build and validation

No separate build or validation metadata was supplied for this measurement directory.
