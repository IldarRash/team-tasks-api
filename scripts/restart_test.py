"""Restart only this Compose project's API; preserve its DB volume."""
import argparse
import json
import subprocess
import time
from pathlib import Path
from verify_api import request, new_team, cleanup


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--output", default="output/restart.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    team = new_team()
    try:
        before = request(args.base, "POST", "/tasks", {"teamId": team, "name": "persistent",
                         "description": "must survive API restart"}, (201,))
        subprocess.run(["docker", "compose", "-p", "team-tasks-api", "restart", "api"], cwd=root, check=True)
        deadline = time.monotonic() + 120
        while True:
            try:
                request(args.base, "GET", "/actuator/health")
                break
            except Exception:
                if time.monotonic() > deadline:
                    raise
                time.sleep(1)
        after = request(args.base, "GET", f'/tasks/{before["id"]}')
        assert before == after, (before, after)
        result = {"passed": True, "operation": "docker compose -p team-tasks-api restart api",
                  "allTaskFieldsPreserved": True}
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
    finally:
        cleanup(args.base, team)
