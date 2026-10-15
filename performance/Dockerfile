FROM team-tasks-api-native

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends strace \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /thread-trace \
    && chown app:app /thread-trace

USER app
ENTRYPOINT ["strace", "-ff", "-ttt", "-T", "-e", "trace=clone,clone3", "-e", "signal=none", "-s", "4096", "--seccomp-bpf", "-o", "/thread-trace/threads", "/app/team-tasks-api"]
