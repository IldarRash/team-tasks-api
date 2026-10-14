# Performance Graph r3

Workflow UF3-TEAM-TASKS-20261014, revision 3, Graph. User approved local Gatling migration, repository cleanup, resource evidence and profile: 1/10/100/1000 teams, 10 seeded tasks/team, 20 concurrent users, 30s warmup + 60s measurement; extra 100-user scenario for 1000 teams. Remote actions excluded. Prior application acceptance remains evidence, not a substitute for Gatling results.

Completion: reproducible Gatling suite, actual results for all five profiles, native HTML reports, thread/heap/native-memory snapshots, JFR, sampled JVM/container metrics, documented rates and limitations, clean local commits and refreshed delivery archive. Generated build/cache directories and obsolete Python load entrypoint removed from active deliverables. Prior Python measurements clearly marked historical.

| Node | Owner / targets | Input | Action / required evidence |
|---|---|---|---|
| P1 | writer / src/gatling/** | approved profile, API contract | Gatling Java SDK scenario, checks and deterministic team distribution; compile + short smoke |
| P2 | root / build, profiling Compose/Docker, performance scripts | approved profile | JDK diagnostics, bounded JVM configuration, sample collector, isolated fixtures and suite runner; capability probe |
| P3 | root / local benchmark runtime | P1 AND P2 succeeded | Five profiles sequentially; warmup excluded; actual Gatling logs/HTML, JFR, JVM snapshots and resource CSV; final dataset invariant |
| P4 | root / performance/results, docs, README | P3 succeeded | Comparison charts and tables, definitions of RPS/TPS/threads/heap/RSS; evidence paths |
| P5 | root / git, archive | P4 succeeded | Cleanup owned generated files, focused regression checks, commits and archive consistency |

Edges: P1/P2 -> P3 (AND); P3 -> P4 -> P5. P1/P2 independent with disjoint ownership; shared build/manifests root only. States pending/ready/running/succeeded/failed/blocked/skipped/awaiting_approval/cancelled. Ready only after inputs and all predecessor evidence exist. Root integrates and owns completion.

Use separate benchmark API/database project; leave normal application data untouched. Start profiling from fresh API process per profile for comparable thread baselines. Collect metrics at bounded cadence, record observer overhead and same-host limitations. Virtual users are not OS threads. Heap used/committed/max, JVM native committed/reserved, process RSS, and Docker memory are different measures. Do not turn sampled maxima into exact lifetime peaks. Full heap dumps optional after measurement due stop-the-world overhead; JFR and heap summaries always collected.

Retries: for failing compile/diagnostic/check, inspect exact error, apply bounded owner fix and rerun affected step, maximum two cycles per cause; then blocked with evidence. No automatic retry of unknown HTTP write outcomes. Keep failed runs separate; only actual successful runs enter comparison. If metrics/JFR tools unavailable, P2 blocked and resolve capability before claiming footprint completion. If safety threshold/container OOM appears, stop current run, save failure evidence and report it; do not silently reduce approved load.

Only owned fixtures/benchmark containers and workspace-generated outputs can be cleaned. No recursive deletion without verifying absolute target is inside this project. Volume deletion, unrelated data changes, remote publish/merge/deployment and messaging are outside scope. Changes to profile/dependencies/recovery/completion require revision and author approval. User's explicit profile approval carries into execution.
