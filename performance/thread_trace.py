"""Strict parser for per-thread ``strace -ff -ttt -T`` clone traces.

The runner writes one file per traced Linux TID (``threads.<tid>``).  A
successful clone/clone3 with ``CLONE_THREAD`` creates exactly one OS thread;
the positive syscall return value is the child TID.  This module deliberately
refuses to turn a partial trace into an exact-count claim.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import re


_TRACE_FILE = re.compile(r"^threads\.(\d+)$")
_STAMP = re.compile(r"^\s*(\d+(?:\.\d+)?)\s+(.*)$")
_CALL = re.compile(r"^(clone3?|clone)\((.*)$")
_RESUMED = re.compile(r"^<\.\.\.\s+(clone3?|clone) resumed>\s*(.*)$")
_RETURN = re.compile(r"\)\s+=\s+(.+?)\s+<([0-9.]+)>\s*$")
_UNFINISHED = re.compile(r"^(clone3?|clone)\((.*)<unfinished \.\.\.>\s*$")


def _ns(value: str) -> int:
    """Convert a decimal seconds value to an integral nanosecond timestamp."""
    try:
        result = Decimal(value) * Decimal(1_000_000_000)
    except InvalidOperation as error:
        raise ValueError(f"invalid decimal timestamp {value!r}") from error
    if result != result.to_integral_value():
        raise ValueError(f"timestamp cannot be represented as whole nanoseconds: {value!r}")
    return int(result)


def _completion(body: str):
    """Return (arguments, result, durationNs), or None for an incomplete call."""
    match = _RETURN.search(body)
    if not match:
        return None
    arguments = body[: match.start() + 1]
    result = match.group(1)
    return arguments, result, _ns(match.group(2))


def _return_value(result: str):
    """Return a valid positive child TID, rejecting decorated/zero results."""
    return int(result) if re.fullmatch(r"[1-9]\d*", result) else None


def _failed(result: str) -> bool:
    # strace renders a failed syscall as -1 followed by an errno token and,
    # usually, its parenthesised description.  Do not silently accept a
    # truncated or otherwise unknown negative result as a known failure.
    return re.fullmatch(r"-1\s+[A-Z][A-Z0-9_]*(?:\s+\([^\r\n]*\))?", result) is not None


def _validation(*, files: int, errors: list[str], unavailable: list[str]) -> dict:
    return {
        "exactCountAvailable": not errors and not unavailable,
        "fatalErrors": errors,
        "unavailableReasons": unavailable,
        "traceFiles": files,
    }


def parse_traces(directory: str | Path) -> dict:
    """Parse ``threads.<tid>`` files beneath *directory*.

    Returns ``events``, ``failedAttempts``, ``nonThreadCounts`` and
    ``validation``.  The result remains inspectable when validation fails;
    consumers must require ``validation['exactCountAvailable']`` before making
    an exact thread-birth claim.

    ``strace`` writes a timestamp at syscall entry for a complete line.  For a
    resumed unfinished line, its timestamp is the return-side timestamp; -T
    supplies the duration, so entry is derived as ``resumed - duration``.  If
    the original unfinished timestamp is available, the two entry timestamps
    must agree to one trace timestamp tick (microsecond for -ttt output).
    """
    root = Path(directory)
    files = sorted(
        (path for path in root.iterdir() if path.is_file() and _TRACE_FILE.match(path.name)),
        key=lambda path: path.name,
    ) if root.is_dir() else []
    if not files:
        return {
            "events": [],
            "failedAttempts": [],
            "nonThreadCounts": {"clone": 0, "clone3": 0},
            "validation": _validation(files=0, errors=[], unavailable=["no threads.<tid> trace files found"]),
        }

    events: list[dict] = []
    failed_attempts: list[dict] = []
    non_thread_counts = {"clone": 0, "clone3": 0}
    errors: list[str] = []

    for path in files:
        parent_tid = int(_TRACE_FILE.match(path.name).group(1))
        pending: dict | None = None
        for line_number, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            stamped = _STAMP.match(raw)
            if not stamped:
                if "clone" in raw:
                    errors.append(f"{path.name}:{line_number}: unparsed clone record")
                continue
            try:
                timestamp_ns = _ns(stamped.group(1))
            except ValueError as error:
                errors.append(f"{path.name}:{line_number}: {error}")
                continue
            text = stamped.group(2)

            unfinished = _UNFINISHED.match(text)
            if unfinished:
                if pending is not None:
                    errors.append(f"{path.name}:{line_number}: nested unfinished clone record")
                pending = {
                    "syscall": unfinished.group(1),
                    "arguments": unfinished.group(2),
                    "entryEpochNs": timestamp_ns,
                    "line": line_number,
                }
                continue

            resumed = _RESUMED.match(text)
            if resumed:
                if pending is None:
                    errors.append(f"{path.name}:{line_number}: resumed clone has no unfinished match")
                    continue
                syscall = resumed.group(1)
                if pending["syscall"] != syscall:
                    errors.append(f"{path.name}:{line_number}: resumed {syscall} mismatches unfinished {pending['syscall']}")
                    pending = None
                    continue
                completion = _completion(resumed.group(2))
                if completion is None:
                    errors.append(f"{path.name}:{line_number}: truncated resumed clone record")
                    pending = None
                    continue
                arguments, result, duration_ns = completion
                entry_ns = timestamp_ns - duration_ns
                # strace -ttt normally has microsecond resolution.  Permit one
                # tick so textual rounding cannot make a complete trace fail.
                if abs(entry_ns - pending["entryEpochNs"]) > 1_000:
                    errors.append(f"{path.name}:{line_number}: resumed timestamp/duration disagrees with unfinished entry")
                _record(parent_tid, syscall, pending["arguments"] + arguments, result, entry_ns, timestamp_ns, events, failed_attempts, non_thread_counts, errors, path.name, line_number)
                pending = None
                continue

            call = _CALL.match(text)
            if call:
                syscall = call.group(1)
                completion = _completion(call.group(2))
                if completion is None:
                    errors.append(f"{path.name}:{line_number}: truncated clone record")
                    continue
                arguments, result, duration_ns = completion
                _record(parent_tid, syscall, arguments, result, timestamp_ns, timestamp_ns + duration_ns, events, failed_attempts, non_thread_counts, errors, path.name, line_number)
                continue

            if "clone" in text:
                errors.append(f"{path.name}:{line_number}: unparsed clone record")

        if pending is not None:
            errors.append(f"{path.name}:{pending['line']}: unfinished clone record has no resumed match")

    return {
        "events": events,
        "failedAttempts": failed_attempts,
        "nonThreadCounts": non_thread_counts,
        "validation": _validation(files=len(files), errors=errors, unavailable=[]),
    }


def _record(parent_tid, syscall, arguments, result, entry_ns, return_ns, events, failed_attempts, non_thread_counts, errors, filename, line_number):
    shared = {
        "parentTid": parent_tid,
        "syscall": syscall,
        "entryEpochNs": entry_ns,
        "returnEpochNs": return_ns,
    }
    if _failed(result):
        failed_attempts.append({**shared, "result": result})
        return
    child_tid = _return_value(result)
    if child_tid is None:
        errors.append(f"{filename}:{line_number}: malformed clone return result {result!r}")
        return
    if "CLONE_THREAD" not in arguments:
        non_thread_counts[syscall] += 1
        return
    events.append({**shared, "childTid": child_tid})


def count_window(events: list[dict], start_min_ns: int, start_max_ns: int, end_min_ns: int, end_max_ns: int) -> dict:
    """Classify births by their whole syscall interval against a measured window.

    A birth is definite only if the entire clone syscall lies in the latest
    possible start and earliest possible end.  Any interval touching uncertain
    boundaries is ambiguous, preventing an exact in-window count claim.
    """
    if start_min_ns > start_max_ns or end_min_ns > end_max_ns or start_min_ns > end_max_ns:
        raise ValueError("invalid measurement-window bounds")
    definite_inside = []
    definite_outside = []
    ambiguous = []
    for event in events:
        entry, returned = event["entryEpochNs"], event["returnEpochNs"]
        if entry >= start_max_ns and returned <= end_min_ns:
            definite_inside.append(event)
        elif returned < start_min_ns or entry > end_max_ns:
            definite_outside.append(event)
        else:
            ambiguous.append(event)
    return {
        # Numeric keys are convenient for summaries; retain event lists for
        # evidence and diagnosis of any conservative-boundary ambiguity.
        "definite": len(definite_inside),
        "outside": len(definite_outside),
        "ambiguous": len(ambiguous),
        "definiteInside": definite_inside,
        "definiteOutside": definite_outside,
        "ambiguousEvents": ambiguous,
        "exactCountAvailable": not ambiguous,
    }
