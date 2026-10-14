# GraalVM Native Image

The native executable implements the same Spring HTTP API and PostgreSQL transaction rules as the JVM application. Build with Docker and an active Linux-container daemon:

```sh
docker build -f native/Dockerfile -t team-tasks-api-native .
```

The first build downloads Gradle, dependencies and the GraalVM builder image. Compilation needs several gigabytes of memory. Runtime limits belong to Compose and are independent of compiler memory. The resulting runtime image runs as UID 10001.

For a matched JVM/native comparison, set JAVA_HOME to JDK 17 and run from the repository root:

```sh
./gradlew bootJar gatlingClasses
python performance/compare_runtimes.py
python performance/render_comparison.py performance/results/jvm-native-comparison
```

On Windows use `gradlew.bat`. The comparison uses localhost port 8082 and its own PostgreSQL database volume. Only one API variant runs at a time. Each profile has a separate warmup and measured Gatling invocation. Restart both comparison services after a source change by rebuilding their images.

Stop comparison containers while retaining data:

```sh
docker compose -p team-tasks-compare -f performance/compare-compose.yaml down
```

The runner records common Linux process and container metrics. JVM-specific heap/JFR/NMT evidence from the separate diagnostic suite is not substituted for native metrics or included in the fair timed comparison.
