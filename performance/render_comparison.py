"""Render an offline dashboard from retained real comparison measurements."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def render(directory):
    directory = Path(directory).resolve()
    payload = json.loads((directory / 'comparison.json').read_text(encoding='utf-8'))
    source = (ROOT / 'performance/dashboard/template.html').read_text(encoding='utf-8')
    assert source.count('__COMPARISON_DATA__') == 1
    (directory / 'index.html').write_text(source.replace('__COMPARISON_DATA__', json.dumps(payload).replace('<', '\\u003c')), encoding='utf-8')
    lines = ['# JVM and GraalVM Native Image: measured comparison', '',
             'Gatling generates the load. One TPS is one successful lifecycle of four HTTP requests.', '',
             '| Teams | Users | Runtime | RPS | TPS | HTTP p95 ms | Lifecycle p95 ms | RSS MiB | OS threads | Errors |',
             '|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    for profile in payload['profiles']:
        for runtime in ['jvm', 'native']:
            r = profile[runtime]
            assert r is not None, f'Missing actual {runtime} measurements'
            lines.append(f"| {profile['teams']} | {profile['users']} | {runtime} | {r['rps']:.2f} | {r['tps']:.2f} | {r['httpP95Ms']} | {r['transactionP95Ms']} | {r['rssMiB']:.1f} | {r['osThreads']} | {r['errors']} |")
    lines += ['', 'Observed changes, Native relative to JVM (one pass per profile):', '', '| Teams | Users | RPS change | RSS change | HTTP p95 change |', '|---:|---:|---:|---:|---:|']
    for p in payload['profiles']:
        j, n = p['jvm'], p['native']
        changes = [100 * (n[key] / j[key] - 1) for key in ['rps', 'rssMiB', 'httpP95Ms']]
        lines.append(f"| {p['teams']} | {p['users']} | {changes[0]:+.1f}% | {changes[1]:+.1f}% | {changes[2]:+.1f}% |")
    lines += ['', 'Both API variants have 2 CPUs, 1 GiB container memory and a 512 MiB maximum heap. PostgreSQL has matching 2 CPU / 1 GiB limits. Ten tasks per team are reset before each run. Warmup is separate from measurement. Each runtime gets a fresh process. Gatling uses the same shared keep-alive connection pool across virtual users for both runtimes. Execution order alternates between JVM-first and Native-first across profiles.', '',
              'RSS, OS threads, container CPU/memory and the Gatling generator footprint are sampled every five seconds. Values are observed maxima, not exact lifetime peaks. JVM-only JFR/NMT profiling is absent from both timed variants. Separate diagnostic captures are not used as the paired baseline.', '',
              'Throughput and latency use Gatling native report statistics. TPS is not the database transaction rate. Virtual users are asynchronous sessions and do not correspond to a dedicated thread each. Docker CPU 200% corresponds to two cores.', '',
              'Startup measures Docker compose up through the first healthy HTTP response and includes orchestration plus one-second polling. Database caches, sequential execution order and shared host scheduling can affect a single pass. Results describe this local workload, not a production capacity guarantee.', '',
              '[Interactive dashboard](index.html) · [Raw comparison](comparison.json)', '']
    lines += ['## Additional footprints', '', '| Teams | Users | Runtime | App startup s | Docker-to-health s | New OS thread IDs observed | Generator RSS MiB | Generator threads |', '|---:|---:|---|---:|---:|---:|---:|---:|']
    for p in payload['profiles']:
        for runtime in ['jvm', 'native']:
            r = p[runtime]
            app = r.get('applicationStartupSeconds')
            gen = r.get('generatorRssMiB')
            lines.append(f"| {p['teams']} | {p['users']} | {runtime} | {app if app is not None else 'unavailable'} | {r['startupSeconds']:.2f} | {r.get('observedNewOsThreads','unavailable')} | {f'{gen:.1f}' if gen is not None else 'unavailable'} | {r.get('generatorOsThreads','unavailable')} |")
    lines += ['', 'New thread IDs are distinct Linux thread IDs first seen in the measurement samples relative to the post-warmup baseline. Threads that start and finish between snapshots are not counted. Generator samples can be missing at process exit; sample coverage is retained in each summary.', '', '## Build and validation', '', '[Native build version and compiler footprint](native-build.json) · [Native HTTP/concurrency/restart validation](native-validation.json) · [PostgreSQL regression tests](regression.json)', '', 'The native compiler and JVM runtime have different Java patch versions; each version and image identity is retained. This comparison measures the two recorded runtime packages, with that version difference as a confounding factor. Compiler RSS is build-time memory, not API runtime RSS. Both variants use the same application code and database rules.', '']
    build_info = directory / 'native-build.json'
    if build_info.exists():
        build = json.loads(build_info.read_text(encoding='utf-8'))
        first = payload['profiles'][0]
        version_path = directory / f"teams-{first['teams']}-users-{first['users']}/jvm/runtime-version.txt"
        version = version_path.read_text(encoding='utf-8') if version_path.exists() else 'unavailable'
        lines += [f"Native: {build['graalVersion']}; target {build['targetMachine']}; {build['gc']}. Native generation: {build['nativeImageGenerationSecondsReported']} s; compiler peak RSS: {build['compilerPeakRssGbReported']} GB.", '', 'Recorded JVM runtime:', '', '```text', version.strip(), '```', '']
    (directory / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    hashes = {str(p.relative_to(directory)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(directory.rglob('*')) if p.is_file() and p.name != 'manifest-sha256.json'}
    (directory / 'manifest-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
    print(f'Rendered {directory}: {len(hashes)} files hashed')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    render(parser.parse_args().directory)
