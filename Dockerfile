FROM ghcr.io/graalvm/native-image-community:17 AS builder
WORKDIR /workspace
RUN microdnf install -y findutils && microdnf clean all

COPY gradle gradle
COPY gradlew settings.gradle.kts build.gradle.kts ./
RUN chmod +x gradlew
COPY src src
ENV MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE=health,metrics
RUN --mount=type=cache,target=/root/.gradle ./gradlew --no-daemon nativeCompile

FROM ubuntu:22.04
WORKDIR /app
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app
COPY --from=builder --chown=app:app /workspace/build/native/nativeCompile/team-tasks-api /app/team-tasks-api

USER app
ENV MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE=health,metrics
EXPOSE 8080
ENTRYPOINT ["/app/team-tasks-api"]
