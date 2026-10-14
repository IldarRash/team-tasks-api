"""Standard-library HTTP acceptance checks. Creates and cleans its own random teams."""
import argparse
import concurrent.futures
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def request(base, method, path, body=None, expected=(200,)):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            code, payload = response.status, response.read()
    except urllib.error.HTTPError as error:
        code, payload = error.code, error.read()
    assert code in expected, (method, path, code, payload.decode())
    return json.loads(payload) if payload else None


def assert_dense(tasks):
    assert [task["priority"] for task in tasks] == list(range(1, len(tasks) + 1)), tasks
    assert len({task["id"] for task in tasks}) == len(tasks)


def new_team():
    return uuid.uuid4().int % 1_000_000_000_000 + 1


def cleanup(base, team):
    for task in request(base, "GET", f"/tasks?teamId={team}"):
        request(base, "DELETE", f'/tasks/{task["id"]}', expected=(204, 404))


def verify(base):
    teams = [new_team(), new_team()]
    checks = []
    def create(team, name):
        return request(base, "POST", "/tasks", {"teamId": team, "name": name,
                       "description": "acceptance check"}, (201,))
    try:
        team = teams[0]
        assert request(base, "GET", f"/tasks?teamId={team}") == []
        tasks = [create(team, name) for name in ["A", "B", "C", "D"]]
        assert_dense(request(base, "GET", f"/tasks?teamId={team}"))
        assert create(teams[1], "independent")["priority"] == 1
        checks.append("creation and independent teams")
        moved = request(base, "PATCH", f'/tasks/{tasks[3]["id"]}/priority', {"priority": 2})
        assert moved["priority"] == 2
        ordered = request(base, "GET", f"/tasks?teamId={team}")
        assert [t["name"] for t in ordered] == ["A", "D", "B", "C"]
        request(base, "PATCH", f'/tasks/{tasks[3]["id"]}/priority', {"priority": 4})
        request(base, "PATCH", f'/tasks/{tasks[3]["id"]}/priority', {"priority": 4})
        assert [t["name"] for t in request(base, "GET", f"/tasks?teamId={team}")] == ["A", "B", "C", "D"]
        checks.append("upward, downward and no-op moves")
        current = request(base, "PATCH", f'/tasks/{tasks[0]["id"]}', {"name": "edited"})
        assert current["description"] == "acceptance check"
        assert current["priority"] == 1
        for invalid in [{}, {"priority": 2}, {"teamId": teams[1]}, {"name": None}, {"description": " "}]:
            error = request(base, "PATCH", f'/tasks/{tasks[0]["id"]}', invalid, (400,))
            assert set(["status", "code", "message", "fieldErrors"]) <= error.keys()
        for priority in [0, -1, 5, 1.5, "2", None]:
            request(base, "PATCH", f'/tasks/{tasks[0]["id"]}/priority', {"priority": priority}, (400,))
        for invalid in [{}, {"teamId": 0, "name": "x", "description": "y"},
                        {"teamId": team, "name": "", "description": "y"},
                        {"teamId": team, "name": "x"},
                        {"teamId": team, "name": "x", "description": "y", "priority": 1}]:
            request(base, "POST", "/tasks", invalid, (400,))
        request(base, "GET", "/tasks/not-a-uuid", expected=(400,))
        request(base, "GET", f"/tasks/{uuid.uuid4()}", expected=(404,))
        checks.append("validation and immutable fields")
        # Delete middle, first, last and final task, checking gaps after each.
        for index in [1, 0, 3, 2]:
            request(base, "DELETE", f'/tasks/{tasks[index]["id"]}', expected=(204,))
            request(base, "GET", f'/tasks/{tasks[index]["id"]}', expected=(404,))
            assert_dense(request(base, "GET", f"/tasks?teamId={team}"))
        assert create(team, "new first")["priority"] == 1
        checks.append("all deletion positions and re-creation")
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            created = list(pool.map(lambda n: create(team, f"parallel-{n}"), range(40)))
        assert len({t["id"] for t in created}) == 40
        assert_dense(request(base, "GET", f"/tasks?teamId={team}"))
        checks.append("40 concurrent creations")
        def mix(index):
            if index % 4 == 0:
                create(team, f"mixed-{index}")
            elif index % 4 == 1:
                request(base, "PATCH", f'/tasks/{created[index % 40]["id"]}/priority',
                        {"priority": 1}, (200, 404))
            elif index % 4 == 2:
                request(base, "DELETE", f'/tasks/{created[index % 40]["id"]}', expected=(204, 404))
            else:
                assert_dense(request(base, "GET", f"/tasks?teamId={team}"))
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            list(pool.map(mix, range(120)))
        assert_dense(request(base, "GET", f"/tasks?teamId={team}"))
        checks.append("120 mixed concurrent writes and snapshot reads")
        return {"passed": True, "checks": checks}
    finally:
        for team in teams:
            cleanup(base, team)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--output", default="output/acceptance.json")
    args = parser.parse_args()
    started = time.perf_counter()
    result = verify(args.base.rstrip("/"))
    result["elapsedSeconds"] = round(time.perf_counter() - started, 3)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
