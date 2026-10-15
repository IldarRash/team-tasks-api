"""Render a native-only exact-thread evidence directory using the standard library."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "performance" / "dashboard" / "template.html"
MANIFEST = "manifest-sha256.json"


def integer(value: Any, missing: str = "—") -> str:
    return missing if value is None else str(int(value))


def decimal(value: Any, places: int = 2) -> str:
    return "—" if value is None else f"{float(value):.{places}f}"


def evidence_path(profile: dict[str, Any], filename: str) -> str:
    return f"teams-{profile['teams']}-users-{profile['users']}/native/{filename}"


def report(payload: dict[str, Any], directory: Path) -> str:
    methodology = payload.get("methodology") or {}
    measurement_seconds = methodology.get("measurementSeconds", 60)
    traced = methodology.get("exactThreadTracing") is True
    lines = [
        "# GraalVM Native Image: точные рождения OS-потоков",
        "",
        "Локальные однопроходные доказательства для Native Image. Это не производственный SLA.",
        "",
        "## Методика",
        "",
        f"- `exactStartedOsThreads` — успешные `clone`/`clone3` с `CLONE_THREAD` в измерительном HTTP-окне Gatling ({measurement_seconds} с; штатный набор использует 60 с).",
        "- `exactTotalStartedOsThreads` — все такие рождения от запуска API до конца захвата трассы. Главный поток API уже существовал до старта трассы, поэтому он не входит в этот счётчик `CLONE_THREAD`.",
        "- Число отдельных API OS-потоков, увиденных tracer с главным потоком, равно `exactTotalStartedOsThreads + 1`; это пояснение границы метода, не отдельная измеренная метрика.",
        "- `exactWarmupStartedOsThreads` может быть `null`: это неопределённая граница warm-up, а не ноль потоков.",
        "- `osThreads` — максимум одновременных потоков, замеченный опросом `/proc/<tracee-pid>/status` каждые 5 с; это не точный lifetime peak.",
        "- Счётчики включают короткоживущие OS, GC, runtime и service threads. Границы HTTP-окна ограничены Gatling и калибровкой часов Docker/Linux.",
        "- RPS под `strace` нельзя напрямую сопоставлять с нетрассируемым запуском.",
        "",
        "Трассировка exact counts: " + ("включена." if traced else "не подтверждена в methodology; точные поля не следует считать доступными."),
    ]
    optional_links = []
    for filename, label in (
        ("verification.json", "offline verification"),
        ("acceptance.json", "native HTTP acceptance"),
        ("restart.json", "native restart check"),
    ):
        if (directory / filename).is_file():
            optional_links.append(f"[{label}]({filename})")
    calibration_dir = directory / "calibration"
    calibration_source = ROOT / "performance" / "calibration.c"
    if calibration_dir.is_dir() and (calibration_dir / "stdout.txt").is_file() and calibration_source.is_file():
        optional_links.append("[calibration stdout](calibration/stdout.txt) · [calibration source](../../calibration.c)")
    if optional_links:
        lines.extend(["", "## Дополнительные доказательства", "", " · ".join(optional_links)])
    lines.extend([
        "",
        "## Профили",
        "",
        "| Команды | Пользователи | RPS | TPS | HTTP p95, мс | RSS, MiB | OS threads max (5 с) | exactStartedOsThreads | exactWarmupStartedOsThreads | exactTotalStartedOsThreads | Ошибки | Исходные файлы |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    for profile in payload.get("profiles", []):
        native = profile.get("native")
        if not isinstance(native, dict):
            lines.append(f"| {profile.get('teams', '—')} | {profile.get('users', '—')} | — | — | — | — | — | — | — | — | — | Нет native summary |")
            continue
        links = " · ".join([
            f"[Gatling]({evidence_path(profile, 'measurement/index.html')})",
            f"[summary]({evidence_path(profile, 'summary.json')})",
            f"[trace parse]({evidence_path(profile, 'thread-trace-parse.json')})",
            f"[clone traces]({evidence_path(profile, 'clone-traces/')})",
            f"[clock calibrations]({evidence_path(profile, 'clock-calibrations.json')})",
        ])
        lines.append(
            f"| {profile['teams']} | {profile['users']} | {decimal(native.get('rps'))} | {decimal(native.get('tps'))} | "
            f"{integer(native.get('httpP95Ms'))} | {decimal(native.get('rssMiB'), 1)} | {integer(native.get('osThreads'))} | "
            f"{integer(native.get('exactStartedOsThreads'))} | {integer(native.get('exactWarmupStartedOsThreads'), 'не определено')} | "
            f"{integer(native.get('exactTotalStartedOsThreads'))} | {integer(native.get('errors'))} | {links} |"
        )
    lines.extend(["", "[Интерактивный dashboard](index.html) · [Исходный comparison.json](comparison.json)", ""])
    return "\n".join(lines)


def render(directory: Path) -> None:
    directory = directory.resolve()
    comparison = directory / "comparison.json"
    if not comparison.is_file():
        raise FileNotFoundError(f"Missing comparison input: {comparison}")
    payload = json.loads(comparison.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("profiles"), list):
        raise ValueError("comparison.json must contain a profiles array")
    source = TEMPLATE.read_text(encoding="utf-8")
    if source.count("__COMPARISON_DATA__") != 1:
        raise ValueError("Dashboard template must contain exactly one comparison-data placeholder")
    javascript_data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    (directory / "index.html").write_text(source.replace("__COMPARISON_DATA__", javascript_data), encoding="utf-8")
    (directory / "report.md").write_text(report(payload, directory), encoding="utf-8")
    manifest = directory / MANIFEST
    hashes = {
        str(path.relative_to(directory)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*")) if path.is_file() and path != manifest
    }
    manifest.write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {directory}: {len(hashes)} files hashed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render native-only exact-thread evidence")
    parser.add_argument("resultdir", type=Path, help="Directory containing comparison.json")
    render(parser.parse_args().resultdir)


if __name__ == "__main__":
    main()
