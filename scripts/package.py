"""Package tracked sources only; never include DB volumes, secrets or build cache."""
import argparse
import subprocess
import zipfile
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/team-tasks-api.zip")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    files = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=root).decode().split("\0")
    out = Path(args.output)
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry in files:
            if entry:
                metadata, name = entry.split("\t", 1)
                mode = metadata.split()[0]
                target = f"team-tasks-api/{name}"
                archive.write(root / name, target)
                info = archive.getinfo(target)
                info.create_system = 3
                info.external_attr = int(mode, 8) << 16
    print(out)
