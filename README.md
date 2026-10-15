# Team Tasks API

Native GraalVM Spring Boot API for creating, listing, updating, reordering, and deleting tasks within teams. Tasks persist in PostgreSQL and have a continuous priority unique within each team. The HTTP contract is [OpenAPI](docs/api.yaml).

## Run

Docker Compose builds the native image tagged `team-tasks-api-native`, starts PostgreSQL, and retains database data in the regular `postgres-data` volume.

```sh
docker compose -p team-tasks-api up --build -d
curl http://localhost:8080/actuator/health
docker compose -p team-tasks-api ps
docker compose -p team-tasks-api logs --tail=100 api
```

The API listens on `http://localhost:8080`; PostgreSQL is bound to `127.0.0.1:55432`. Both services use the local exercise credentials in `compose.yaml`. Stop the stack with `docker compose -p team-tasks-api down`. Do not add `-v` unless you intend to remove the persisted database volume.

The native build uses GraalVM Native Image and can need several GiB of memory during compilation. The running API receives `-Xms256m -Xmx512m`; these are native-image runtime memory options, not a JVM process.

## API

```sh
curl -i -X POST http://localhost:8080/tasks \
  -H 'Content-Type: application/json' \
  -d '{"teamId":1,"name":"First task","description":"Implement endpoint"}'
curl 'http://localhost:8080/tasks?teamId=1'
curl -X PATCH http://localhost:8080/tasks/TASK_ID/priority \
  -H 'Content-Type: application/json' -d '{"priority":1}'
curl -i -X DELETE http://localhost:8080/tasks/TASK_ID
```

POST returns `201` and a Location header. Reads and PATCH return `200`; DELETE returns `204`. Creation rejects a supplied priority. PATCH accepts name and/or description, preserving omitted fields. Team IDs must be positive 64-bit integers; name and description must be nonblank and are limited to 200 and 10,000 UTF-16 code units. See [the OpenAPI contract](docs/api.yaml) for every endpoint and error response.

Moving a task shifts its neighbours: `[A:1,B:2,C:3,D:4]`, moving D to 2 produces `[A:1,D:2,B:3,C:4]`. Requests acquire a per-team transaction lock, so the service preserves continuous priorities across concurrent API instances.

## Tests

Docker startup needs no host JDK. For local tests install JDK 17, set `JAVA_HOME`, and use the checked-in Gradle wrapper.

```sh
./gradlew test
docker compose -p team-tasks-api up -d db
RUN_POSTGRES_INTEGRATION=true ./gradlew test --rerun-tasks
```

PowerShell:

```powershell
.\gradlew.bat test
docker compose -p team-tasks-api up -d db
$env:RUN_POSTGRES_INTEGRATION='true'
.\gradlew.bat test --rerun-tasks
Remove-Item Env:RUN_POSTGRES_INTEGRATION
```

The unit suite does not prove database behaviour. The second command enables PostgreSQL integration tests; its report is at `build/reports/tests/test/index.html`.

## Native performance run

Build the native API once, then run the native-only Gatling matrix and render its exact output directory:

```sh
docker build -t team-tasks-api-native .
python performance/run_native.py
```

The runner prints a fresh UTC evidence directory. Verify and render that exact path; see the [performance guide](performance/README.md) for commands, prerequisites, retained evidence, and the bundled reference result.

On Windows, use `gradlew.bat` when a Gradle preparation step is needed. The matrix covers 1, 10, 100, and 1,000 teams with 20 concurrent users, plus 1,000 teams with 100 users. Each team starts with 10 tasks; every user repeatedly creates a task, changes its priority, lists the team, and deletes that task.

RPS counts successful HTTP requests. TPS counts successful four-request task lifecycles, so they are different units. RSS is process-resident memory; it is not heap or Docker working-set memory. Five-second OS-thread figures and memory maxima are sampled concurrency observations, not lifetime peaks. `exactStartedOsThreads` separately counts successful `CLONE_THREAD` births within the precise HTTP window; the initial main thread is excluded because it was not created by a traced clone. The native run is a local benchmark, not a production capacity guarantee.
