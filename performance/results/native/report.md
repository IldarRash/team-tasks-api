# GraalVM Native Image: точные рождения OS-потоков

Локальные однопроходные доказательства для Native Image. Это не производственный SLA.

## Методика

- `exactStartedOsThreads` — успешные `clone`/`clone3` с `CLONE_THREAD` в измерительном HTTP-окне Gatling (60 с; штатный набор использует 60 с).
- `exactTotalStartedOsThreads` — все такие рождения от запуска API до конца захвата трассы. Главный поток API уже существовал до старта трассы, поэтому он не входит в этот счётчик `CLONE_THREAD`.
- Число отдельных API OS-потоков, увиденных tracer с главным потоком, равно `exactTotalStartedOsThreads + 1`; это пояснение границы метода, не отдельная измеренная метрика.
- `exactWarmupStartedOsThreads` может быть `null`: это неопределённая граница warm-up, а не ноль потоков.
- `osThreads` — максимум одновременных потоков, замеченный опросом `/proc/<tracee-pid>/status` каждые 5 с; это не точный lifetime peak.
- Счётчики включают короткоживущие OS, GC, runtime и service threads. Границы HTTP-окна ограничены Gatling и калибровкой часов Docker/Linux.
- RPS под `strace` нельзя напрямую сопоставлять с нетрассируемым запуском.

Трассировка exact counts: включена.

## Дополнительные доказательства

[offline verification](verification.json) · [native HTTP acceptance](acceptance.json) · [native restart check](restart.json) · [calibration stdout](calibration/stdout.txt) · [calibration source](../../calibration.c)

## Профили

| Команды | Пользователи | RPS | TPS | HTTP p95, мс | RSS, MiB | OS threads max (5 с) | exactStartedOsThreads | exactWarmupStartedOsThreads | exactTotalStartedOsThreads | Ошибки | Исходные файлы |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 20 | 314.03 | 78.51 | 101 | 219.7 | 33 | 2 | 12 | 35 | 0 | [Gatling](teams-1-users-20/native/measurement/index.html) · [summary](teams-1-users-20/native/summary.json) · [trace parse](teams-1-users-20/native/thread-trace-parse.json) · [clone traces](teams-1-users-20/native/clone-traces/) · [clock calibrations](teams-1-users-20/native/clock-calibrations.json) |
| 10 | 20 | 421.18 | 105.30 | 93 | 218.2 | 39 | 1 | 17 | 41 | 0 | [Gatling](teams-10-users-20/native/measurement/index.html) · [summary](teams-10-users-20/native/summary.json) · [trace parse](teams-10-users-20/native/thread-trace-parse.json) · [clone traces](teams-10-users-20/native/clone-traces/) · [clock calibrations](teams-10-users-20/native/clock-calibrations.json) |
| 100 | 20 | 463.93 | 115.98 | 87 | 216.5 | 40 | 1 | 17 | 41 | 0 | [Gatling](teams-100-users-20/native/measurement/index.html) · [summary](teams-100-users-20/native/summary.json) · [trace parse](teams-100-users-20/native/thread-trace-parse.json) · [clone traces](teams-100-users-20/native/clone-traces/) · [clock calibrations](teams-100-users-20/native/clock-calibrations.json) |
| 1000 | 20 | 457.64 | 114.41 | 87 | 213.2 | 41 | 1 | 18 | 42 | 0 | [Gatling](teams-1000-users-20/native/measurement/index.html) · [summary](teams-1000-users-20/native/summary.json) · [trace parse](teams-1000-users-20/native/thread-trace-parse.json) · [clone traces](teams-1000-users-20/native/clone-traces/) · [clock calibrations](teams-1000-users-20/native/clock-calibrations.json) |
| 1000 | 100 | 415.93 | 103.98 | 962 | 285.8 | 124 | 2 | 100 | 125 | 0 | [Gatling](teams-1000-users-100/native/measurement/index.html) · [summary](teams-1000-users-100/native/summary.json) · [trace parse](teams-1000-users-100/native/thread-trace-parse.json) · [clone traces](teams-1000-users-100/native/clone-traces/) · [clock calibrations](teams-1000-users-100/native/clock-calibrations.json) |

[Интерактивный dashboard](index.html) · [Исходный comparison.json](comparison.json)
