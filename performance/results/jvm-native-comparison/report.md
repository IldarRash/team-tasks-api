# JVM and GraalVM Native Image: measured comparison

Gatling generates the load. One TPS is one successful lifecycle of four HTTP requests.

| Teams | Users | Runtime | RPS | TPS | HTTP p95 ms | Lifecycle p95 ms | RSS MiB | OS threads | Errors |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20 | jvm | 486.62 | 121.66 | 65 | 196 | 303.1 | 46 | 0 |
| 1 | 20 | native | 480.07 | 120.02 | 65 | 194 | 199.3 | 33 | 0 |
| 10 | 20 | jvm | 799.21 | 199.80 | 78 | 177 | 308.4 | 47 | 0 |
| 10 | 20 | native | 1080.39 | 270.10 | 62 | 100 | 168.9 | 35 | 0 |
| 100 | 20 | jvm | 812.52 | 203.13 | 78 | 175 | 316.2 | 49 | 0 |
| 100 | 20 | native | 1186.36 | 296.59 | 64 | 91 | 171.7 | 34 | 0 |
| 1000 | 20 | jvm | 842.23 | 210.56 | 77 | 170 | 311.7 | 47 | 0 |
| 1000 | 20 | native | 1152.79 | 288.20 | 64 | 93 | 195.3 | 34 | 0 |
| 1000 | 100 | jvm | 734.89 | 183.72 | 288 | 823 | 337.3 | 135 | 0 |
| 1000 | 100 | native | 1113.44 | 278.36 | 185 | 503 | 263.9 | 117 | 0 |

Observed changes, Native relative to JVM (one pass per profile):

| Teams | Users | RPS change | RSS change | HTTP p95 change |
|---:|---:|---:|---:|---:|
| 1 | 20 | -1.3% | -34.2% | +0.0% |
| 10 | 20 | +35.2% | -45.2% | -20.5% |
| 100 | 20 | +46.0% | -45.7% | -17.9% |
| 1000 | 20 | +36.9% | -37.4% | -16.9% |
| 1000 | 100 | +51.5% | -21.8% | -35.8% |

Both API variants have 2 CPUs, 1 GiB container memory and a 512 MiB maximum heap. PostgreSQL has matching 2 CPU / 1 GiB limits. Ten tasks per team are reset before each run. Warmup is separate from measurement. Each runtime gets a fresh process. Gatling uses the same shared keep-alive connection pool across virtual users for both runtimes. Execution order alternates between JVM-first and Native-first across profiles.

RSS, OS threads, container CPU/memory and the Gatling generator footprint are sampled every five seconds. Values are observed maxima, not exact lifetime peaks. JVM-only JFR/NMT profiling is absent from both timed variants. Separate diagnostic captures are not used as the paired baseline.

Throughput and latency use Gatling native report statistics. TPS is not the database transaction rate. Virtual users are asynchronous sessions and do not correspond to a dedicated thread each. Docker CPU 200% corresponds to two cores.

Startup measures Docker compose up through the first healthy HTTP response and includes orchestration plus one-second polling. Database caches, sequential execution order and shared host scheduling can affect a single pass. Results describe this local workload, not a production capacity guarantee.

[Interactive dashboard](index.html) · [Raw comparison](comparison.json)

## Additional footprints

| Teams | Users | Runtime | App startup s | Docker-to-health s | New OS thread IDs observed | Generator RSS MiB | Generator threads |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 20 | jvm | 7.392 | 7.64 | 2 | 343.9 | 70 |
| 1 | 20 | native | 0.473 | 2.01 | 3 | 358.6 | 67 |
| 10 | 20 | jvm | 7.392 | 7.80 | 1 | 338.5 | 68 |
| 10 | 20 | native | 0.473 | 1.46 | 3 | 361.8 | 69 |
| 100 | 20 | jvm | 7.392 | 7.56 | 1 | 335.5 | 69 |
| 100 | 20 | native | 0.473 | 2.40 | 1 | 343.2 | 69 |
| 1000 | 20 | jvm | 7.392 | 7.58 | 1 | 359.2 | 69 |
| 1000 | 20 | native | 0.473 | 2.21 | 2 | 346.1 | 69 |
| 1000 | 100 | jvm | 7.392 | 7.69 | 6 | 347.2 | 69 |
| 1000 | 100 | native | 0.473 | 1.80 | 3 | 361.8 | 66 |

New thread IDs are distinct Linux thread IDs first seen in the measurement samples relative to the post-warmup baseline. Threads that start and finish between snapshots are not counted. Generator samples can be missing at process exit; sample coverage is retained in each summary.

## Build and validation

[Native build version and compiler footprint](native-build.json) · [Native HTTP/concurrency/restart validation](native-validation.json) · [PostgreSQL regression tests](regression.json)

The native compiler and JVM runtime have different Java patch versions; each version and image identity is retained. This comparison measures the two recorded runtime packages, with that version difference as a confounding factor. Compiler RSS is build-time memory, not API runtime RSS. Both variants use the same application code and database rules.

Native: GraalVM CE 17.0.9+9.1; target x86-64-v3; Serial GC. Native generation: 153 s; compiler peak RSS: 5.04 GB.

Recorded JVM runtime:

```text
Picked up JAVA_TOOL_OPTIONS: -Xms256m -Xmx512m -XX:ActiveProcessorCount=2
openjdk version "17.0.20.1" 2026-08-18
OpenJDK Runtime Environment Temurin-17.0.20.1+1 (build 17.0.20.1+1)
OpenJDK 64-Bit Server VM Temurin-17.0.20.1+1 (build 17.0.20.1+1, mixed mode, sharing)
```
