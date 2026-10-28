"""Build one committed study runtime in a fresh directory; never reinstall it.

Run through run_heavy.py. The source archive, wheel, interpreter environment,
and checker copies belong exclusively to this build. Rebuild into a new path.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args()
    if not os.environ.get("ARC_HEAVY_CPUS"):
        parser.error("run this build through scripts/run_heavy.py --cpus N")
    repo = Path(__file__).resolve().parents[1]
    revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", args.revision + "^{commit}"], cwd=repo, text=True).strip()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    done = 0
    stages = 5

    def progress(label):
        elapsed = time.monotonic() - started
        rate = done / elapsed if elapsed else 0
        eta = f"{(stages-done)/rate:.0f}s" if rate else "pending"
        print(f"{done}/{stages} stages; elapsed={elapsed:.1f}s "
              f"rate={rate:.3f} stages/s ETA={eta}; {label}", flush=True)

    def run(command, label, **kwargs):
        nonlocal done
        progress(label)
        # Inherit stdout/stderr: build output is streamed, with heartbeats
        # even while a compiler step emits nothing.
        with subprocess.Popen([str(x) for x in command], **kwargs) as process:
            while True:
                try:
                    code = process.wait(timeout=2)
                    break
                except subprocess.TimeoutExpired:
                    progress(label)
            if code:
                raise subprocess.CalledProcessError(code, command)
        done += 1
        progress(label + " finished")

    source = destination / "source"
    source.mkdir()
    archive = destination / "source.tar"
    run(["git", "archive", "--format=tar", "-o", archive, revision,
         "engine", "scripts/study"], "archive " + revision, cwd=repo)
    run(["tar", "-xf", archive, "-C", source], "extract committed source")
    checks = destination / "checks"
    shutil.copytree(source / "scripts/study", checks)
    wheels = destination / "wheels"
    env = dict(os.environ, CARGO_TARGET_DIR=str(destination / "target"),
               CARGO_BUILD_JOBS=os.environ["ARC_HEAVY_CPUS"], PYTHONDONTWRITEBYTECODE="1")
    run(["maturin", "build", "--offline", "--profile", "tool", "--manifest-path",
         source / "engine/arclog-py/Cargo.toml", "--interpreter", sys.executable,
         "--out", wheels], "build isolated wheel", env=env)
    venv = destination / "venv"
    run([sys.executable, "-B", "-m", "venv", venv], "create private environment")
    built = list(wheels.glob("arclog-*.whl"))
    if len(built) != 1:
        raise RuntimeError(f"expected exactly one wheel, got {built}")
    run(["uv", "pip", "install", "--python", venv / "bin/python", "--no-deps",
         built[0]], "install private wheel")
    manifest = dict(revision=revision, wheel=str(built[0]), python=str(venv / "bin/python"),
                    checks=str(checks), seconds=time.monotonic()-started)
    (destination / "ready.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    main()
