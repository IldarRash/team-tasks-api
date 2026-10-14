"""Decode the pinned Gatling 3.13.5 binary log to aggregate real HTTP/group events.

Format source: Gatling v3.13.5 LogFileDataWriter.scala (big-endian fields,
compact Java strings and shared cached labels). Reject unsupported versions.
"""
import collections
import math
import struct
from pathlib import Path


class Reader:
    def __init__(self, data):
        self.data, self.pos, self.cache = data, 0, {}

    def number(self, code):
        value = struct.unpack_from(">" + code, self.data, self.pos)[0]
        self.pos += struct.calcsize(code)
        return value

    def text(self):
        size = self.number("i")
        if size == 0:
            return ""
        data = self.data[self.pos:self.pos+size]
        self.pos += size
        coder = self.number("B")
        if coder != 0:
            raise ValueError("Only Latin1 event labels supported by this parser")
        return data.decode("latin-1")

    def cached(self):
        key = self.number("i")
        if key < 0:
            return self.cache[-key]
        self.cache[key] = self.text()
        return self.cache[key]

    def groups(self):
        return [self.cached() for _ in range(self.number("i"))]


def percentiles(values):
    values = sorted(values)
    return {f"p{p}": values[max(0, math.ceil(len(values)*p/100)-1)] for p in [50, 95, 99]}


def parse(path):
    r = Reader(Path(path).read_bytes())
    assert r.number("B") == 0
    version = r.text()
    if version != "3.13.5":
        raise ValueError(f"Unsupported log version {version}")
    simulation, epoch = r.text(), r.number("q")
    description = r.text()
    scenarios = [r.text() for _ in range(r.number("i"))]
    for _ in range(r.number("i")):
        size = r.number("i")
        r.pos += size
    requests, transactions, errors = [], [], []
    users_started = users_ended = 0
    while r.pos < len(r.data):
        record = r.number("B")
        if record == 1:
            groups, name = r.groups(), r.cached()
            start, end, ok, error = r.number("i"), r.number("i"), r.number("B"), r.cached()
            requests.append((name, start, end, ok))
            if not ok:
                errors.append(error)
        elif record == 2:
            scenario, started, timestamp = r.number("i"), r.number("B"), r.number("i")
            users_started += started
            users_ended += 1-started
        elif record == 3:
            groups = r.groups()
            start, end, cumulative, ok = r.number("i"), r.number("i"), r.number("i"), r.number("B")
            if groups == ["Task lifecycle"]:
                transactions.append((start, end, ok))
        elif record == 4:
            errors.append(r.cached())
            r.number("i")
        else:
            raise ValueError(f"Unsupported record {record} at {r.pos}")
    assert requests and transactions
    start, end = min(t[1] for t in requests), max(t[2] for t in requests)
    seconds = (end-start)/1000
    successful = sum(t[3] for t in requests)
    successful_groups = sum(t[2] for t in transactions)
    per_request = {}
    for name in sorted({t[0] for t in requests}):
        rows = [t for t in requests if t[0] == name]
        per_request[name] = {"requests": len(rows), "failed": sum(not t[3] for t in rows),
                             "latencyMs": percentiles([t[2]-t[1] for t in rows])}
    result = {"version": version, "simulation": simulation,
              "startEpochMs": epoch+start, "endEpochMs": epoch+end,
              "observedHttpSeconds": seconds, "requests": len(requests),
              "successfulRequests": successful, "failedRequests": len(requests)-successful,
              "successfulTransactions": successful_groups,
              "failedTransactions": len(transactions)-successful_groups,
              "rps": successful/seconds, "tps": successful_groups/seconds,
              "httpLatencyMs": percentiles([t[2]-t[1] for t in requests]),
              "transactionLatencyMs": percentiles([t[1]-t[0] for t in transactions]),
              "perRequest": per_request, "errors": dict(collections.Counter(errors)),
              "usersStarted": users_started, "usersEnded": users_ended}
    assert result["failedRequests"] == 0 and result["failedTransactions"] == 0 and not errors, result
    assert len(requests) == len(transactions)*4
    return result
